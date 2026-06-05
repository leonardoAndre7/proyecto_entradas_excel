"""
Asigna el número impreso a los lotes EXISTENTES leyéndolo de un PDF.
Empareja por geometría (el número que cae dentro del polígono del lote),
así NO se pierden estados, precios ni separaciones.

Uso:  python manage.py asignar_numeros "C:\\ruta\\al\\PLANO.pdf"
       python manage.py asignar_numeros "...pdf" --dry-run     (solo reporta, no guarda)
"""
from django.core.management.base import BaseCommand, CommandError
from lotes.models import Lote, Plano, punto_en_poligono


class Command(BaseCommand):
    help = "Asigna números de lote desde un PDF a los lotes existentes (por geometría)."

    def add_arguments(self, parser):
        parser.add_argument("pdf", type=str, help="Ruta al PDF del plano")
        parser.add_argument("--dry-run", action="store_true", help="No guarda, solo reporta")

    def handle(self, *args, **opts):
        try:
            import fitz
        except ImportError:
            raise CommandError("pymupdf no está instalado.")

        ruta = opts["pdf"]
        dry  = opts["dry_run"]

        doc  = fitz.open(ruta)
        page = doc[0]

        # Palabras numéricas con el centro de su caja
        palabras = []
        for w in page.get_text("words"):
            x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4].strip()
            if txt and any(c.isdigit() for c in txt):
                palabras.append(((x0 + x1) / 2.0, (y0 + y1) / 2.0, txt))
        doc.close()

        plano = Plano.objects.first()
        lotes = Lote.objects.filter(plano=plano) if plano else Lote.objects.all()

        asignados = 0
        sin_numero = []
        for lote in lotes:
            if not lote.puntos or len(lote.puntos) < 3:
                continue
            numero = None
            for (wx, wy, wt) in palabras:
                if punto_en_poligono(wx, wy, lote.puntos):
                    numero = wt
                    if wt.isdigit():
                        break
            if numero:
                if not dry:
                    lote.numero = numero
                    lote.save(update_fields=["numero"])
                asignados += 1
            else:
                sin_numero.append(lote.id)

        total = lotes.count()
        self.stdout.write(self.style.SUCCESS(
            f"\n{'(DRY-RUN) ' if dry else ''}Lotes con número asignado: {asignados} / {total}"
        ))
        if sin_numero:
            self.stdout.write(
                f"Sin número ({len(sin_numero)}) → IDs: {sin_numero[:40]}"
                + (" ..." if len(sin_numero) > 40 else "")
            )
            self.stdout.write("  (esos se corrigen a mano o se bloquean con 'No disponible')")
