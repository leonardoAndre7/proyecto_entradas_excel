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
from decimal import Decimal

# ==========================================
# 🏢 NUEVO MODELO: EVENTO (SaaS MULTI-TENANT)
# ==========================================
def ahora_actual():
    """Hora actual (aislada para poder simular fechas en pruebas sin afectar sesiones)."""
    from django.utils import timezone
    return timezone.now()


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

    # 📅 Acceso por días: cuántos días distintos puede ingresar esta entrada (1 ingreso por día)
    dias_validos = models.PositiveSmallIntegerField(default=1, verbose_name="Días de acceso (ingresos permitidos)")
    # 🕒 Ventana horaria opcional (vacío = sin restricción de hora)
    hora_desde = models.TimeField(blank=True, null=True, verbose_name="Ingreso permitido desde")
    hora_hasta = models.TimeField(blank=True, null=True, verbose_name="Ingreso permitido hasta")
    # 📅 Vigencia por fechas (opcional): la entrada solo sirve entre estas fechas (inclusive)
    fecha_desde = models.DateField(blank=True, null=True, verbose_name="Válida desde (fecha)")
    fecha_hasta = models.DateField(blank=True, null=True, verbose_name="Válida hasta (fecha)")

    def __str__(self):
        return f"{self.tipo_entrada} (S/ {self.preventa_1} - S/ {self.puerta}) - {self.evento.nombre}"

    @property
    def vigencia_texto(self):
        if self.fecha_desde and self.fecha_hasta:
            return f"{self.fecha_desde:%d/%m/%Y} al {self.fecha_hasta:%d/%m/%Y}"
        if self.fecha_desde:
            return f"desde el {self.fecha_desde:%d/%m/%Y}"
        if self.fecha_hasta:
            return f"hasta el {self.fecha_hasta:%d/%m/%Y}"
        return ""

    @property
    def ventana_horaria_texto(self):
        if self.hora_desde and self.hora_hasta:
            return f"{self.hora_desde.strftime('%H:%M')} - {self.hora_hasta.strftime('%H:%M')}"
        if self.hora_desde:
            return f"desde {self.hora_desde.strftime('%H:%M')}"
        if self.hora_hasta:
            return f"hasta {self.hora_hasta.strftime('%H:%M')}"
        return ""


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

    # Datos que llegan desde la hoja de ventas (Google Sheets) por la API
    metodo_pago = models.CharField(max_length=60, blank=True, null=True, verbose_name="Método de pago")
    voucher_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Enlace al comprobante")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas / detalle de la venta")
    referencia_externa = models.CharField(max_length=100, blank=True, null=True, db_index=True,
                                          verbose_name="Referencia externa (fila de la hoja)")

    # Separaciones y pagos en partes: cada pago queda en PagoParticipante; aquí va el acumulado
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"),
                                       verbose_name="Monto pagado acumulado")
    autorizado_por = models.CharField(max_length=120, blank=True, null=True,
                                      verbose_name="Descuento / cortesía autorizado por")

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

    # ------------------------------------------------------------------
    # 📅 Control de ingresos por día (multi-día, configurable por tarifa)
    # ------------------------------------------------------------------
    @property
    def saldo_pendiente(self):
        """Lo que falta pagar. Solo aplica a ventas con pagos registrados (separaciones)."""
        if not self.pk or not self.pagos.exists():
            return Decimal("0.00")
        return max((self.total_pagar or Decimal("0")) - (self.monto_pagado or Decimal("0")), Decimal("0.00"))

    @property
    def en_separacion(self):
        """Tiene un saldo por pagar y contabilidad aún no la dio por pagada."""
        return (not self.pago_confirmado) and self.saldo_pendiente > 0

    def _tarifa_efectiva(self):
        if self.tarifa_id:
            return self.tarifa
        if self.evento_id and self.tipo_entrada:
            return Tarifa.objects.filter(evento=self.evento, tipo_entrada__iexact=self.tipo_entrada).first()
        return None

    def fechas_ingreso(self):
        """Lista de datetimes de ingreso. Incluye el ingreso histórico (previo a esta función)."""
        fechas = list(self.ingresos.order_by('fecha_hora').values_list('fecha_hora', flat=True))
        if not fechas and self.entrada_usada:
            # Ingreso anterior a esta función: se sabe que entró, pero no cuándo
            fechas = [None]
        return fechas

    @property
    def ultimo_ingreso(self):
        return next((f for f in reversed(self.fechas_ingreso()) if f), None)

    @property
    def ingresos_limite(self):
        tarifa = self._tarifa_efectiva()
        return max(tarifa.dias_validos, 1) if tarifa else 1

    @property
    def ingresos_hechos(self):
        return len(self.fechas_ingreso())

    @property
    def puede_ingresar_mas(self):
        return self.ingresos_hechos < self.ingresos_limite

    def registrar_ingreso(self):
        """
        Registra un ingreso con la fila bloqueada: así dos puertas (o la puerta y el escaneo
        con login) no pueden registrar a la vez la misma entrada. Ver _registrar_ingreso.
        """
        from django.db import transaction
        if not self.pk:
            return self._registrar_ingreso()
        with transaction.atomic():
            Participante.objects.select_for_update(of=("self",)).filter(pk=self.pk).first()
            self.refresh_from_db(fields=['entrada_usada'])
            return self._registrar_ingreso()

    def _registrar_ingreso(self):
        """
        Intenta registrar un ingreso ahora. Devuelve (ok, mensaje).
        Reglas: máximo `tarifa.dias_validos` ingresos, uno por día calendario,
        y dentro de la ventana horaria de la tarifa si está definida.
        """
        import datetime
        from django.utils import timezone

        tarifa = self._tarifa_efectiva()
        limite = max(tarifa.dias_validos, 1) if tarifa else 1
        ahora = ahora_actual()
        local = timezone.localtime(ahora)

        self.ultimo_motivo = None   # duplicado | agotado | fuera_de_horario | fuera_de_fecha | saldo_pendiente
        if self.en_separacion:
            self.ultimo_motivo = "saldo_pendiente"
            return False, (f"💰 Pago incompleto: tiene un saldo pendiente de S/ {self.saldo_pendiente:,.2f}. "
                           "Debe completar el pago antes de ingresar.")
        if tarifa:
            hoy = local.date()
            if tarifa.fecha_desde and hoy < tarifa.fecha_desde:
                self.ultimo_motivo = "fuera_de_fecha"
                return False, f"📅 Esta entrada ({tarifa.tipo_entrada}) todavía no es válida: ingresa desde el {tarifa.fecha_desde:%d/%m/%Y}."
            if tarifa.fecha_hasta and hoy > tarifa.fecha_hasta:
                self.ultimo_motivo = "fuera_de_fecha"
                return False, f"📅 Esta entrada ({tarifa.tipo_entrada}) ya venció: era válida hasta el {tarifa.fecha_hasta:%d/%m/%Y}."
            if tarifa.hora_desde and local.time() < tarifa.hora_desde:
                self.ultimo_motivo = "fuera_de_horario"
                return False, f"⏰ Fuera de horario: esta entrada ({tarifa.tipo_entrada}) ingresa {tarifa.ventana_horaria_texto}."
            if tarifa.hora_hasta and local.time() > tarifa.hora_hasta:
                self.ultimo_motivo = "fuera_de_horario"
                return False, f"⏰ Fuera de horario: esta entrada ({tarifa.tipo_entrada}) ingresa {tarifa.ventana_horaria_texto}."

        fechas = self.fechas_ingreso()
        for f in fechas:
            if f and timezone.localtime(f).date() == local.date():
                self.ultimo_motivo = "duplicado"
                return False, f"❌ ¡Boleto ya utilizado hoy! Registrado el {timezone.localtime(f).strftime('%d/%m/%Y %I:%M %p')}"

        if len(fechas) >= limite:
            self.ultimo_motivo = "agotado"
            ultima = next((f for f in reversed(fechas) if f), None)
            detalle = f" Último ingreso: {timezone.localtime(ultima).strftime('%d/%m/%Y %I:%M %p')}" if ultima else ""
            return False, f"❌ ¡Boleto ya utilizado! Agotó sus {limite} día(s) de acceso.{detalle}"

        # Si venía de un registro histórico sin fila, conservarlo antes de sumar el nuevo
        if not self.ingresos.exists() and self.entrada_usada:
            # Ingreso histórico sin fecha guardada: se conserva como 1 día ya usado
            # (fechado el día anterior, ya que no se sabe cuándo ocurrió).
            IngresoParticipante.objects.create(participante=self, fecha_hora=ahora - datetime.timedelta(days=1))
        IngresoParticipante.objects.create(participante=self, fecha_hora=ahora)
        if not self.entrada_usada:
            self.entrada_usada = True
            self.save(update_fields=['entrada_usada'])
        dia = len(fechas) + 1
        extra = f" (día {dia} de {limite})" if limite > 1 else ""
        return True, f"✅ ¡Acceso Autorizado! Bienvenido al evento{extra}."


class IngresoParticipante(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="ingresos")
    fecha_hora = models.DateTimeField()

    class Meta:
        ordering = ['fecha_hora']

    def __str__(self):
        return f"{self.participante_id} - {self.fecha_hora:%d/%m/%Y %H:%M}"


# ==========================================
# 💵 PAGOS DE UNA ENTRADA (separaciones / pagos en partes)
# ==========================================
class PagoParticipante(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="pagos")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=60, blank=True, null=True)
    voucher_url = models.URLField(max_length=500, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    registrado_por = models.CharField(max_length=255, blank=True, null=True)
    referencia_externa = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    class Meta:
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.participante_id} - S/ {self.monto}"


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


# ==========================================
# 💾 RESPALDO EN BASE DE DATOS DE ARCHIVOS SUBIDOS
# ==========================================
class ArchivoMedia(models.Model):
    """
    Copia en la base de datos de los archivos subidos (fondo/logo/banner del evento y
    comprobantes de pago). Render borra el disco en cada despliegue o reinicio; con esta copia
    los archivos se restauran solos (ver media_respaldo.py).
    """
    ruta = models.CharField(max_length=500, unique=True)
    contenido = models.BinaryField()
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ruta


# ==========================================
# 🚪 CÓDIGOS DE PUERTA (app de escaneo sin login)
# ==========================================
class CodigoPuerta(models.Model):
    """
    Acceso de un dispositivo de puerta. Solo permite validar entradas del evento asignado.
    El código se guarda como hash (HMAC): el valor en claro solo se muestra al crearlo.
    """
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="codigos_puerta")
    nombre = models.CharField(max_length=80, verbose_name="Dispositivo / persona")
    codigo_hash = models.CharField(max_length=64, unique=True, editable=False)
    activo = models.BooleanField(default=True)
    vence_en = models.DateTimeField(verbose_name="Vence")
    creado = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)
    escaneos = models.PositiveIntegerField(default=0)

    ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O/1/I para evitar confusiones

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return f"{self.nombre} - {self.evento.nombre}"

    @staticmethod
    def hash_codigo(codigo):
        import hashlib, hmac
        limpio = (codigo or "").strip().upper().replace("-", "").replace(" ", "")
        return hmac.new(settings.SECRET_KEY.encode(), limpio.encode(), hashlib.sha256).hexdigest()

    @classmethod
    def generar(cls, evento, nombre, vence_en):
        """Crea el código y devuelve (objeto, codigo_en_claro)."""
        import secrets
        codigo = "".join(secrets.choice(cls.ALFABETO) for _ in range(8))
        obj = cls.objects.create(evento=evento, nombre=nombre, vence_en=vence_en,
                                 codigo_hash=cls.hash_codigo(codigo))
        return obj, f"{codigo[:4]}-{codigo[4:]}"

    @property
    def vigente(self):
        return self.activo and ahora_actual() < self.vence_en

    @staticmethod
    def vencimiento_por_defecto(evento, horas_extra=6):
        """Fin del último día del evento + horas_extra (si el evento no tiene fecha: 3 días)."""
        import datetime
        from django.utils import timezone
        fechas = [f for f in [evento.fecha_evento, *evento.tarifas.values_list('fecha_hasta', flat=True)] if f]
        if fechas:   # último día del evento (considera las fechas de las tarifas: eventos de 2 días)
            fin = datetime.datetime.combine(max(fechas) + datetime.timedelta(days=1), datetime.time(0, 0))
            fin = timezone.make_aware(fin, timezone.get_current_timezone())
        else:
            fin = ahora_actual() + datetime.timedelta(days=3)
        return fin + datetime.timedelta(hours=horas_extra)
