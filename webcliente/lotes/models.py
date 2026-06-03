import os
import logging
from django.db import models

logger = logging.getLogger(__name__)


class Plano(models.Model):
    nombre = models.CharField(max_length=100)
    imagen = models.FileField(
        upload_to="planos/",
        help_text="Sube la imagen del plano (PNG, JPG) o un archivo PDF. Los PDFs se convierten a imagen automáticamente."
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Si el archivo subido es PDF → convertir a PNG automáticamente
        if self.imagen and self.imagen.name.lower().endswith('.pdf'):
            self._convertir_pdf_a_png()

    def _convertir_pdf_a_png(self):
        """Convierte la primera página del PDF a PNG y actualiza el campo imagen."""
        try:
            import fitz  # pymupdf
        except ImportError:
            logger.error("pymupdf no está instalado. No se puede convertir el PDF.")
            return

        pdf_path = self.imagen.path
        try:
            doc = fitz.open(pdf_path)
            page = doc[0]  # Primera página

            # Renderizar a 2x resolución (144 DPI) para buena calidad
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            doc.close()

            # Guardar PNG junto al PDF original
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            png_filename = base_name + '.png'
            png_path = os.path.join(os.path.dirname(pdf_path), png_filename)
            pix.save(png_path)

            # Actualizar el campo en BD para apuntar al PNG
            relative_png = 'planos/' + png_filename
            Plano.objects.filter(pk=self.pk).update(imagen=relative_png)
            self.imagen.name = relative_png

            # Eliminar el PDF original (ya no se necesita)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            logger.info(f"PDF convertido a PNG: {png_path}")

        except Exception as e:
            logger.error(f"Error convirtiendo PDF a PNG: {e}", exc_info=True)

    def __str__(self):
        return self.nombre


class Lote(models.Model):

    plano = models.ForeignKey(Plano, on_delete=models.CASCADE)

    # 🔥 NUEVO: guardar polígono
    puntos = models.JSONField(null=True, blank=True)

    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    width = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)

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
