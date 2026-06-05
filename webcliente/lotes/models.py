import os
import logging
from django.db import models
from django.conf import settings

logger = logging.getLogger(__name__)

ESCALA_PNG = 1.0  # Matrix(1,1) — mínimo uso de memoria para Render Starter (512MB)


def punto_en_poligono(px, py, puntos):
    """Ray casting. `puntos` = lista de dicts {'x','y'} o tuplas (x,y)."""
    def xy(p):
        return (p['x'], p['y']) if isinstance(p, dict) else (p[0], p[1])
    inside = False
    n = len(puntos); j = n - 1
    for i in range(n):
        xi, yi = xy(puntos[i]); xj, yj = xy(puntos[j])
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


class Plano(models.Model):
    nombre = models.CharField(max_length=100)
    imagen = models.FileField(
        upload_to="planos/",
        help_text="Sube la imagen del plano (PNG, JPG) o un archivo PDF. "
                  "Los PDFs se convierten a imagen y los lotes se importan automáticamente."
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Si el archivo subido es PDF → convertir + importar lotes en hilo separado
        if self.imagen and self.imagen.name.lower().endswith('.pdf'):
            import threading
            t = threading.Thread(target=self._procesar_pdf, daemon=True)
            t.start()

    def _procesar_pdf(self):
        """
        Al subir un PDF:
          1. Convierte la página 1 a PNG (2x resolución)
          2. Extrae los polígonos de los lotes y los importa en la BD
          3. Borra el PDF original
        """
        try:
            import fitz  # pymupdf
        except ImportError:
            logger.error("pymupdf no está instalado. No se puede procesar el PDF.")
            return

        import gc
        pdf_path = self.imagen.path
        try:
            doc  = fitz.open(pdf_path)
            page = doc[0]

            # ── 1. CONVERTIR A PNG ──────────────────────────────────────────
            mat = fitz.Matrix(ESCALA_PNG, ESCALA_PNG)
            pix = page.get_pixmap(matrix=mat, alpha=False)  # alpha=False ahorra memoria

            base_name    = os.path.splitext(os.path.basename(pdf_path))[0]
            png_filename = base_name + '.png'
            png_path     = os.path.join(os.path.dirname(pdf_path), png_filename)
            pix.save(png_path)
            del pix   # liberar memoria del pixel buffer
            gc.collect()

            relative_png = 'planos/' + png_filename
            Plano.objects.filter(pk=self.pk).update(imagen=relative_png)
            self.imagen.name = relative_png
            logger.info(f"PDF → PNG: {png_path}")

            # ── 2. EXTRAER LOTES ────────────────────────────────────────────
            lotes_data = self._extraer_lotes_de_pdf(page, doc)
            doc.close()

            # Borrar lotes anteriores de este plano y crear los nuevos
            from lotes.models import Lote  # import aquí para evitar circular
            Lote.objects.filter(plano=self).delete()
            creados = 0
            for ld in lotes_data:
                Lote.objects.create(
                    plano=self,
                    puntos=ld['puntos'],
                    numero=ld.get('numero'),
                    estado='disponible',
                )
                creados += 1
            logger.info(f"Lotes importados: {creados}")

        except Exception as e:
            logger.error(f"Error procesando PDF: {e}", exc_info=True)
            try:
                doc.close()
            except Exception:
                pass
            return

        # ── 3. BORRAR PDF ORIGINAL ──────────────────────────────────────────
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    @staticmethod
    def _extraer_lotes_de_pdf(page, doc):
        """
        Extrae polígonos de los lotes del plano PDF.
        Retorna lista de {'puntos': [{x, y}, ...]}
        con coordenadas ya escaladas al PNG (×ESCALA_PNG).
        """
        paths  = page.get_drawings()
        page_w = page.rect.width
        page_h = page.rect.height

        # Palabras numéricas con el centro de su caja (para asignar el número a cada lote)
        palabras_num = []
        for w in page.get_text('words'):
            x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4].strip()
            if txt and any(ch.isdigit() for ch in txt):
                palabras_num.append(((x0 + x1) / 2.0, (y0 + y1) / 2.0, txt))

        # ── Recopilar polígonos rellenos (tipo 'f') ──
        poligonos = []
        for p in paths:
            if p.get('type') != 'f':
                continue
            items = p.get('items', [])
            if not items:
                continue

            puntos_pdf = []
            if items[0][0] == 're':  # rectángulo simple
                r = items[0][1]
                puntos_pdf = [
                    {'x': r.x0, 'y': r.y0}, {'x': r.x1, 'y': r.y0},
                    {'x': r.x1, 'y': r.y1}, {'x': r.x0, 'y': r.y1},
                ]
            else:  # polígono con líneas
                for item in items:
                    if item[0] in ('m', 'l'):
                        puntos_pdf.append({'x': item[1].x, 'y': item[1].y})

            if len(puntos_pdf) < 3:
                continue

            xs = [pt['x'] for pt in puntos_pdf]
            ys = [pt['y'] for pt in puntos_pdf]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            # Ignorar marcos gigantes (> 10 % del área total de la página)
            if area > page_w * page_h * 0.10:
                continue

            centroide = {'x': sum(xs)/len(xs), 'y': sum(ys)/len(ys)}
            # Buscar el número impreso que cae dentro de este polígono
            numero = None
            for (wx, wy, wt) in palabras_num:
                if punto_en_poligono(wx, wy, puntos_pdf):
                    numero = wt
                    if wt.isdigit():   # preferimos un número puro
                        break
            poligonos.append({'puntos': puntos_pdf, 'centroide': centroide, 'numero': numero})

        # ── Escalar coordenadas al PNG ──
        lotes = []
        for pol in poligonos:
            puntos_png = [
                {'x': round(pt['x'] * ESCALA_PNG, 1),
                 'y': round(pt['y'] * ESCALA_PNG, 1)}
                for pt in pol['puntos']
            ]
            lotes.append({'puntos': puntos_png, 'numero': pol.get('numero')})

        return lotes

    def __str__(self):
        return self.nombre


class Lote(models.Model):

    plano  = models.ForeignKey(Plano, on_delete=models.CASCADE)
    puntos = models.JSONField(null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)  # número impreso del lote

    x      = models.FloatField(null=True, blank=True)
    y      = models.FloatField(null=True, blank=True)
    width  = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=[
            ("disponible", "Disponible"),
            ("vendido",    "Vendido"),
            ("reservado",  "Reservado"),
            ("bloqueado",  "Bloqueado"),  # zonas que NO son lotes (caminos, lagunas, etc.)
        ],
        default="disponible"
    )

    # Quién separó (reservó) el lote. Solo el admin o esta persona pueden desecharlo.
    separado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="lotes_separados",
    )

    # Precio del lote (esquineros, tamaños distintos, etc.)
    precio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Marcas de tiempo
    separado_en = models.DateTimeField(null=True, blank=True)  # cuándo se separó
    vendido_en  = models.DateTimeField(null=True, blank=True)  # cuándo se vendió

    def __str__(self):
        return f"Lote {self.id}"


class TipoCambio(models.Model):
    """Cotización USD→PEN cacheada. Se refresca desde una API y sirve de respaldo."""
    usd_pen     = models.DecimalField(max_digits=8, decimal_places=4, default=3.75)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"USD→PEN {self.usd_pen} ({self.actualizado:%d/%m/%Y %H:%M})"


class MovimientoLote(models.Model):
    """Historial simple: registra cada cambio de estado de un lote (quién y cuándo)."""
    lote    = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name="movimientos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    estado  = models.CharField(max_length=20)   # estado al que pasó
    fecha   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        u = self.usuario.username if self.usuario_id else "—"
        return f"Lote {self.lote_id}: {self.estado} por {u} ({self.fecha:%d/%m/%Y %H:%M})"
