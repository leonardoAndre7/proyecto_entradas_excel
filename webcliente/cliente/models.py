from django.db import models
import qrcode
from django.conf import settings
from io import BytesIO
from django.core.files import File
import uuid
import secrets
import os
from PIL import Image
from django.db import models


#########################################
##########################################
###########################################
#PREVIA DEL DESPERTAR DEL EMPRENDEDOR
###########################################
###########################################



from django.db import models
from django.db.models import Max
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image
import os
from django.urls import reverse
from django.conf import settings
from uuid import uuid4





class Previaparticipantes(models.Model):
    cod_part = models.CharField(max_length=100, unique=True, blank=True)
    nombres = models.CharField(max_length=255, blank=True, null=True)
    dni = models.CharField(max_length=20, blank=True, null=True)
    celular = models.CharField(max_length=9, blank=True, null=True)
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
                # Construir link de validación
                link_validacion = f"{settings.BASE_URL}{reverse('validar_entrada_previo', args=[str(self.token)])}"

                # Generar QR
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(link_validacion)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGBA')

                # Abrir imagen base (si existe)
                base_path = os.path.join(settings.BASE_DIR, "cliente", "static", "img", "previaqr.jpg")
                if os.path.exists(base_path):
                    base_img = Image.open(base_path).convert("RGBA")
                    qr_width = 720 - 322
                    qr_height = 1492 - 1110
                    img_qr = img_qr.resize((qr_width, qr_height))
                    position = (322, 1110)
                    base_img.paste(img_qr, position, img_qr)
                else:
                    base_img = img_qr

                # Guardar imagen en memoria y asignarla al ImageField
                buffer = BytesIO()
                base_img.save(buffer, format="PNG")
                file_name = f"{self.cod_part}_qr.png"
                self.qr_image.save(file_name, File(buffer), save=False)

            except Exception as e:
                print("⚠️ Error generando QR:", e)

        # Guardar finalmente (solo una vez)
        super().save(*args, **kwargs)
        
        
        
        
        
        
        
        

class Voucher(models.Model):
    # Se relaciona opcionalmente con Participante o Previaparticipantes
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
        return "Voucher sin participante asignado"

##################################################################################
##################################################################################
##################################################################################
### MODELO DE LOS EMAIL ENVIADOS 
##################################################################################
##################################################################################
##################################################################################

class EmailEnviado(models.Model):
    participante = models.ForeignKey(Previaparticipantes, on_delete=models.CASCADE, related_name="emails")
    destinatario = models.EmailField()
    asunto = models.CharField(max_length=255)
    cuerpo_html = models.TextField()
    
    enviado = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)
    
    message_id = models.CharField(max_length=255, blank=True, null=True, help_text="Mesaage ID de SendGrid")
    
    fecha_envio = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.destinatario} - {self.asunto}"













###############################################
###########################################
###################################################

class Participante(models.Model):
    TIPO_ENTRADA_CHOICES = [
        ("FULL ACCESS", "Full Access"),
        ("EMPRESARIAL", "Empresarial"),
        ("EMPRENDEDOR", "Emprendedor"),
    ]


    cod_cliente = models.CharField(max_length=100, unique=True, editable=False)
    nombres = models.CharField(max_length=100, blank=True, null=True)
    apellidos = models.CharField(max_length=100, blank=True, null=True)
    dni = models.CharField(max_length=20, blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    correo = models.CharField(max_length=50, blank=True, null=True)
    vendedor = models.CharField(max_length=255, blank=True, null=True)

    tipo_entrada = models.CharField(
        max_length=20,
        choices=TIPO_ENTRADA_CHOICES
    )
    paquete = models.CharField(max_length=100, blank=True, null=True)
    cantidad = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    qr = models.ImageField(upload_to='qr/', null=True, blank=True)
    pago_confirmado = models.BooleanField(default=False)
    usado = models.BooleanField(default=False)
    entrada_usada = models.BooleanField(default=False)
    token = models.CharField(max_length=64, unique=True, editable=False, blank=True)

    # 🔹 Validaciones adicionales
    validado_admin = models.BooleanField(default=False)
    validado_contabilidad = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # 🔹 Si tipo_entrada está definido, asignar precio automáticamente
        # 🔹 Asignar precio automáticamente solo si no se puso precio manual
        if not self.precio:
            if self.tipo_entrada in self.PRECIOS_ENTRADA:
                self.precio = self.PRECIOS_ENTRADA[self.tipo_entrada]

        # 🔹 Calcular total
        self.total_pagar = (self.cantidad or 0) * (self.precio or 0)

        # 🔹 Generar cod_cliente
        if not self.cod_cliente:
            prefix = (self.tipo_entrada or "PARTICIPANTE").replace(" ", "").upper()
            last_code = Participante.objects.filter(cod_cliente__startswith=prefix).order_by("-cod_cliente").first()
            last_number = 1
            if last_code:
                try:
                    last_number = int(last_code.cod_cliente[len(prefix):]) + 1
                except ValueError:
                    last_number = 1
            self.cod_cliente = f"{prefix}{last_number:03d}"

        # 🔹 Generar token único
        if not self.token:
            self.token = uuid.uuid4().hex

        # 🔹 Guardar temporalmente para obtener PK antes de QR
        if not self.pk:
            super().save(*args, **kwargs)

        # 🔹 Generar QR
        base_url = settings.BASE_URL.rstrip("/")
        qr_content = f"{base_url}/validar/{self.pk}/{self.token}"

        qr_img = qrcode.make(qr_content)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        self.qr.save(f"{self.dni or self.cod_cliente}.png", File(buffer), save=False)

        super().save(*args, **kwargs)


class RegistroCorreo(models.Model):
        participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
        fecha_envio = models.DateTimeField(auto_now_add=True)
        enviado = models.BooleanField(default=False)
        mensaje = models.TextField(blank=True)

        def __str__(self):
            return f"{self.destinatario} - {self.asunto}"
