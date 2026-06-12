from django.db import models
from django.contrib.auth.models import User
import qrcode
from django.conf import settings
from io import BytesIO
from django.core.files import File
import uuid
import os
from PIL import Image
from django.urls import reverse
from uuid import uuid4

# ==========================================
# 🏢 NUEVO MODELO: EVENTO (SaaS MULTI-TENANT)
# ==========================================
class Evento(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Evento")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    fecha_evento = models.DateField(blank=True, null=True, verbose_name="Fecha del Evento")
    
    # 📧 Configuración de Correo (SMTP Dinámico por Evento)
    smtp_host = models.CharField(max_length=255, default="smtp.sendgrid.net", verbose_name="Servidor SMTP")
    smtp_port = models.IntegerField(default=587, verbose_name="Puerto SMTP")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="Usar TLS")
    smtp_user = models.CharField(max_length=255, default="apikey", verbose_name="Usuario SMTP")
    smtp_password = models.CharField(max_length=255, blank=True, null=True, verbose_name="Contraseña SMTP / API Key")
    default_from_email = models.CharField(
        max_length=255, 
        default="Soporte Círculo 50k <soporte.circulo50k@hilariogrp.com>", 
        verbose_name="Remitente por Defecto"
    )
    
    # 🎟️ Límites de Inventario y Antireventa
    aforo_maximo = models.IntegerField(default=500, verbose_name="Aforo Máximo")
    limite_entradas_persona = models.IntegerField(default=5, verbose_name="Límite de Entradas por Persona")
    
    # 📱 Configuración WhatsApp (Dinámico & Extensible)
    whatsapp_provider = models.CharField(
        max_length=20, 
        default='INACTIVE', 
        choices=[
            ('INACTIVE', 'Inactivo'),
            ('TWILIO', 'Twilio (Legacy)'),
            ('CUSTOM_API', 'Custom API Gateway (YCloud, Whapi, etc.)')
        ],
        verbose_name="Proveedor de WhatsApp"
    )
    whatsapp_api_url = models.CharField(max_length=500, blank=True, null=True, verbose_name="URL de la API de WhatsApp")
    whatsapp_api_headers = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Cabeceras HTTP (Key: Value por línea)",
        help_text="Ej:\nAuthorization: Bearer mi-token\nX-API-Key: mi-key"
    )
    whatsapp_api_payload = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Cuerpo JSON de la API (Payload)",
        help_text="Puedes usar variables como: {celular}, {nombres}, {evento}, {entradas}, {url_imagen}"
    )

    twilio_account_sid = models.CharField(max_length=255, blank=True, null=True, verbose_name="Twilio Account SID")
    twilio_auth_token = models.CharField(max_length=255, blank=True, null=True, verbose_name="Twilio Auth Token")
    twilio_whatsapp_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número WhatsApp Twilio")
    twilio_phone_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número Teléfono Twilio")
    imgbb_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="ImgBB API Key")
    
    # 🎨 Personalización Estética (White-Label)
    color_primario = models.CharField(max_length=7, default="#7b1fa2", verbose_name="Color de Interfaz (HEX)")
    logo = models.ImageField(upload_to="event_logos/", blank=True, null=True, verbose_name="Logo del Evento")
    imagen_fondo = models.ImageField(upload_to="event_backgrounds/", blank=True, null=True, verbose_name="Fondo del Boleto (asesor.jpeg)")
    banner = models.ImageField(upload_to="event_banners/", blank=True, null=True, verbose_name="Banner de Cabecera")

    # 🔲 Configuración del QR en el boleto (editor visual)
    qr_pos_x       = models.IntegerField(default=168,      verbose_name="QR Posición X (px)")
    qr_pos_y       = models.IntegerField(default=405,      verbose_name="QR Posición Y (px)")
    qr_ancho       = models.IntegerField(default=567,      verbose_name="QR Ancho (px)")
    qr_alto        = models.IntegerField(default=569,      verbose_name="QR Alto (px)")
    qr_color_frente = models.CharField(max_length=7, default="#000000", verbose_name="QR Color frente")
    qr_color_fondo  = models.CharField(max_length=20, default="#ffffff", verbose_name="QR Color fondo")
    qr_fuente       = models.CharField(max_length=50, default="Roboto-Bold.ttf", verbose_name="Fuente del nombre")

    def __img_fondo_path(self):
        if self.imagen_fondo:
            return self.imagen_fondo.path
        return None

    def __str__(self):
        return self.nombre


# ==========================================
# 💰 NUEVO MODELO: TARIFA (PRECIOS DINÁMICOS)
# ==========================================
class Tarifa(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="tarifas")
    tipo_entrada = models.CharField(max_length=100, verbose_name="Tipo de Entrada (VIP, General, etc.)")
    
    # Precios de las distintas etapas de preventa
    preventa_1 = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Precio Preventa 1")
    preventa_2 = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Precio Preventa 2")
    preventa_3 = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Precio Preventa 3")
    puerta = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Precio Puerta")

    def __str__(self):
        return f"{self.tipo_entrada} (S/ {self.preventa_1} - S/ {self.puerta}) - {self.evento.nombre}"


# ==========================================
# 🔒 NUEVO MODELO: PERFIL DE USUARIO (ROLES)
# ==========================================
class PerfilUsuario(models.Model):
    ROLES = [
        ('SUPERADMIN', 'Super Administrador (Toma todo)'),
        ('ORGANIZADOR', 'Organizador de Empresa (Gestión de Evento)'),
        ('REGISTRADOR', 'Registrador de Entradas / Validador (Puerta)'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=ROLES, default='REGISTRADOR', verbose_name="Rol de Usuario")
    eventos = models.ManyToManyField(Evento, blank=True, related_name="usuarios_autorizados", verbose_name="Eventos Asignados")

    # 🔐 Google OAuth2 — Gmail Conectado para envío de entradas
    google_email = models.EmailField(blank=True, null=True, verbose_name="Gmail Conectado (OAuth2)")
    google_refresh_token = models.TextField(blank=True, null=True, verbose_name="Google Refresh Token")

    @property
    def tiene_gmail_conectado(self):
        return bool(self.google_email and self.google_refresh_token)

    def __str__(self):
        return f"{self.user.username} - {self.get_rol_display()}"


# ==========================================
# 🎟️ MODELO PREVIAPARTICIPANTES (ACTUALIZADO)
# ==========================================
class Previaparticipantes(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="previa_participantes", null=True, blank=True)
    cod_part = models.CharField(max_length=100, blank=True)
    nombres = models.CharField(max_length=255, blank=True, null=True)
    dni = models.CharField(max_length=20, blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    qr_image = models.ImageField(upload_to='qrs/', blank=True, null=True)

    entrada_usada = models.BooleanField(default=False)
    hora_ingreso = models.DateTimeField(null=True, blank=True)

    # Token único para QR
    token = models.UUIDField(default=uuid4, editable=False, unique=True)
    fecha_validacion = models.DateTimeField(blank=True, null=True)
    enviado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # 1️⃣ Generar cod_part si no existe
        if not self.cod_part:
            if not self.id:
                super().save(*args, **kwargs)  # Guardar para obtener ID
            self.cod_part = f"CLI{self.id:03d}"

        # 2️⃣ Generar QR solo si no existe
        if not self.qr_image:
            try:
                base_url = settings.BASE_URL.rstrip("/")
                link_validacion = f"{base_url}/validar/{self.token}/"

                # Generar QR
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(link_validacion)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGBA')

                # Abrir imagen base
                base_path = os.path.join(settings.BASE_DIR, "cliente", "static", "img", "previaqr.jpg")
                if self.evento and self.evento.imagen_fondo:
                    base_path = self.evento.imagen_fondo.path
                
                if os.path.exists(base_path):
                    base_img = Image.open(base_path).convert("RGBA")
                    qr_width = 720 - 322
                    qr_height = 1492 - 1110
                    img_qr = img_qr.resize((qr_width, qr_height))
                    position = (322, 1110)
                    base_img.paste(img_qr, position, img_qr)
                else:
                    base_img = img_qr

                # Guardar imagen en memoria
                buffer = BytesIO()
                base_img.save(buffer, format="PNG")
                file_name = f"{self.cod_part}_qr.png"
                self.qr_image.save(file_name, File(buffer), save=False)

            except Exception as e:
                print("⚠️ Error generando QR previa:", e)

        super().save(*args, **kwargs)


# ==========================================
# 🎟️ MODELO PARTICIPANTE (ACTUALIZADO)
# ==========================================
class Participante(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="participantes", null=True, blank=True)
    tarifa = models.ForeignKey(Tarifa, on_delete=models.SET_NULL, related_name="participantes", null=True, blank=True)
    
    cod_cliente = models.CharField(max_length=100, unique=True, editable=False)
    nombres = models.CharField(max_length=100, blank=True, null=True)
    apellidos = models.CharField(max_length=100, blank=True, null=True)
    dni = models.CharField(max_length=20, blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    correo = models.CharField(max_length=100, blank=True, null=True)
    vendedor = models.CharField(max_length=255, blank=True, null=True)

    tipo_entrada = models.CharField(max_length=100, blank=True, null=True)
    paquete = models.CharField(max_length=100, blank=True, null=True)
    cantidad = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    qr = models.ImageField(upload_to='qr/', null=True, blank=True)
    pago_confirmado = models.BooleanField(default=False)
    usado = models.BooleanField(default=False)
    entrada_usada = models.BooleanField(default=False)
    token = models.CharField(max_length=64, unique=True, editable=False, blank=True)

    validado_admin = models.BooleanField(default=False)
    validado_contabilidad = models.BooleanField(default=False)
    email_enviado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # 🔹 Calcular total
        self.total_pagar = (self.cantidad or 0) * (self.precio or 0)

        # 🔹 Generar tipo_entrada basado en la tarifa
        if self.tarifa and not self.tipo_entrada:
            self.tipo_entrada = self.tarifa.tipo_entrada

        # 🔹 Generar cod_cliente con orden NUMÉRICO real (evita duplicados en el registro 10, 100, etc.)
        if not self.cod_cliente:
            from django.db.models import Max, IntegerField
            from django.db.models.functions import Cast, Substr
            prefix = (self.tipo_entrada or "PARTICIPANTE").replace(" ", "").upper()
            result = (
                Participante.objects
                .filter(cod_cliente__startswith=prefix)
                .annotate(num=Cast(Substr('cod_cliente', len(prefix) + 1), IntegerField()))
                .aggregate(max_num=Max('num'))
            )
            last_number = (result['max_num'] or 0) + 1
            self.cod_cliente = f"{prefix}{last_number:03d}"

        # 🔹 Generar token único
        if not self.token:
            self.token = uuid.uuid4().hex

        # 🔹 Guardar temporalmente para obtener PK antes del QR
        is_new = not self.pk
        if is_new:
            super().save(*args, **kwargs)

        # 🔹 Generar QR de validación solo si aún no existe
        if not self.qr:
            base_url = settings.BASE_URL.rstrip("/")
            qr_content = f"{base_url}/validar/{self.token}/"

            qr_img = qrcode.make(qr_content)
            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            self.qr.save(f"{self.dni or self.cod_cliente}.png", File(buffer), save=False)

        if is_new:
            kwargs.pop('force_insert', None)
            kwargs.pop('force_update', None)
        super().save(*args, **kwargs)


# ==========================================
# 📎 MODELO VOUCHER (RELACIONADO)
# ==========================================
class Voucher(models.Model):
    participante = models.ForeignKey(
        'Participante',
        on_delete=models.CASCADE,
        related_name='vouchers',
        blank=True,
        null=True
    )
    previaparticipante = models.ForeignKey(
        'Previaparticipantes',
        on_delete=models.CASCADE,
        related_name='vouchers_previa',
        blank=True,
        null=True
    )
    imagen = models.ImageField(upload_to='vouchers/')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.participante:
            return f"Voucher de {self.participante.nombres or self.participante.cod_cliente}"
        elif self.previaparticipante:
            return f"Voucher de {self.previaparticipante.nombres or self.previaparticipante.cod_part}"
        return "Voucher sin participante"


# ==========================================
# 📧 MODELO EMAILENVIADO (ACTUALIZADO)
# ==========================================
class EmailEnviado(models.Model):
    participante = models.ForeignKey(Previaparticipantes, on_delete=models.CASCADE, related_name="emails")
    destinatario = models.EmailField()
    asunto = models.CharField(max_length=255)
    cuerpo_html = models.TextField()
    adjunto = models.ImageField(upload_to='email_adjuntos/', blank=True, null=True)
    enviado = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)
    message_id = models.CharField(max_length=255, blank=True, null=True, help_text="Message ID de SendGrid")
    fecha_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.destinatario} - {self.asunto}"


# ==========================================
# 📧 MODELO REGISTROCORREO (ACTUALIZADO)
# ==========================================
class RegistroCorreo(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    enviado = models.BooleanField(default=False)
    mensaje = models.TextField(blank=True)

    def __str__(self):
        return f"{self.participante.nombres} - {self.enviado}"
