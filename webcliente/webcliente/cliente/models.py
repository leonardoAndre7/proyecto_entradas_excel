from django.db import models
import qrcode
from django.conf import settings
from io import BytesIO
from django.core.files import File
import uuid
import secrets


class Participante(models.Model):
    TIPO_ENTRADA_CHOICES = [
        ("FULL ACCES", "Full Acces"),
        ("EMPRESARIAL", "Empresarial"),
        ("EMPRENDEDOR", "Emprendedor"),
    ]

    PRECIOS_ENTRADA = {
    "FULL ACCES": 1050.00,
    "EMPRESARIAL": 525.00,
    "EMPRENDEDOR": 105.00, 
   }

    cod_cliente = models.CharField(max_length=100, unique=True, editable=False)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, unique=True)
    celular = models.CharField(max_length=20)
    correo = models.CharField(max_length=50)
    tipo_entrada = models.CharField(
        max_length=20,
        choices=TIPO_ENTRADA_CHOICES,
        default="FULL ACCES"
    )
    paquete = models.CharField(max_length=100, blank=True, null=True)
    cantidad = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    qr = models.ImageField(upload_to='qr/', null=True, blank=True)
    pago_confirmado = models.BooleanField(default=False)
    usado = models.BooleanField(default=False)
    entrada_usada = models.BooleanField(default=False)
    token = models.CharField(max_length=64, unique=True, editable=False, blank=True)


    def save(self, *args, **kwargs):

        # 🔹 Asignar precio automáticamente según tipo_entrada
        if self.tipo_entrada in self.PRECIOS_ENTRADA:
            self.precio = self.PRECIOS_ENTRADA[self.tipo_entrada]

        # 🔹 Calcular total
        self.total_pagar = (self.cantidad or 0) * (self.precio or 0)

            # Generar cod_cliente automático si no existe
        if not self.cod_cliente:
            prefix = self.tipo_entrada.replace(" ", "").upper()  # Ej: EMPRESARIAL, FULLACCES
            last_code = (
                Participante.objects.filter(cod_cliente__startswith=prefix)
                .order_by("-cod_cliente")
                .first()
            )
            if last_code:
                try:
                    last_number = int(last_code.cod_cliente[len(prefix):])
                except ValueError:
                    last_number = 0
                new_number = last_number + 1
            else:
                new_number = 1

            self.cod_cliente = f"{prefix}{new_number:03d}"

        # Generar token unico si no existe
        if not self.token:
            self.token = uuid.uuid4().hex

        base_url = settings.BASE_URL.rstrip("/")  # quitar "/" final si lo hay
        qr_content = f"{base_url}/validar/{self.pk or ''}/{self.token}"

        # 🔹 Generar QR
        qr_img = qrcode.make(qr_content)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)  # 👈 Esto es MUY importante

        self.qr.save(f"{self.dni}.png", File(buffer), save=False)


        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

class RegistroCorreo(models.Model):
        participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
        fecha_envio = models.DateTimeField(auto_now_add=True)
        enviado = models.BooleanField(default=False)
        mensaje = models.TextField(blank=True)

        def __str__(self):
            return f"{self.participante.nombres} - {self.fecha_envio}"
