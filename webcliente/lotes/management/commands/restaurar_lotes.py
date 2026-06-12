import json
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Restaura los 428 lotes del plano desde el respaldo versionado en el repo'

    def handle(self, *args, **options):
        from lotes.models import Plano, Lote

        plano = Plano.objects.first()
        if not plano:
            self.stderr.write('No hay ningún Plano. Crea uno primero desde el admin y sube la imagen del plano.')
            return

        fixture = os.path.join(settings.BASE_DIR, 'lotes', 'fixtures', 'lotes_respaldo.json')
        if not os.path.exists(fixture):
            self.stderr.write(f'No se encontró el fixture: {fixture}')
            return

        with open(fixture, encoding='utf-8') as f:
            data = json.load(f)

        antes = Lote.objects.filter(plano=plano).count()
        Lote.objects.filter(plano=plano).delete()

        lotes = [
            Lote(
                plano=plano,
                numero=ld['numero'],
                puntos=ld['puntos'],
                x=ld['x'], y=ld['y'],
                width=ld['width'], height=ld['height'],
                estado=ld['estado'],
                precio=Decimal(ld['precio']) if ld['precio'] is not None else None,
            )
            for ld in data['lotes']
        ]
        Lote.objects.bulk_create(lotes)
        despues = Lote.objects.filter(plano=plano).count()

        self.stdout.write(self.style.SUCCESS(
            f'OK — Borrados {antes} lotes, creados {despues} lotes en plano [{plano.id}] "{plano.nombre}"'
        ))
