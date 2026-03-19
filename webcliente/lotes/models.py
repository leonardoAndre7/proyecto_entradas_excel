from django.db import models

class Plano(models.Model):
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to="planos/")

    def __str__(self):
        return self.nombre


class Lote(models.Model):

    plano = models.ForeignKey(Plano, on_delete=models.CASCADE)

    x = models.FloatField()
    y = models.FloatField()

    width = models.FloatField()
    height = models.FloatField()

    estado = models.CharField(
        max_length=20,
        choices=[
            ("disponible","Disponible"),
            ("vendido","Vendido"),
            ("reservado","Reservado")
        ],
        default="disponible"
    )

    def __str__(self):
        return f"Lote {self.id}"