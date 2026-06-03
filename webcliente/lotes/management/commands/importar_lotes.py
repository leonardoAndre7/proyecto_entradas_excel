"""
Comando: python manage.py importar_lotes
Importa los lotes del plano desde el archivo lotes_data.json
incluido en el proyecto. Borra los lotes anteriores del plano activo.
"""
import json
import os
from django.core.management.base import BaseCommand
from lotes.models import Plano, Lote


class Command(BaseCommand):
    help = 'Importa los lotes del plano desde lotes_data.json'

    def handle(self, *args, **options):
        plano = Plano.objects.first()
        if not plano:
            self.stderr.write('❌ No hay ningún plano en la BD. Sube el PNG primero en el admin.')
            return

        self.stdout.write(f'Plano: {plano.nombre} (id={plano.id})')

        # Ruta del JSON incluido en el proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        json_path = os.path.join(base_dir, 'lotes_data.json')

        if not os.path.exists(json_path):
            self.stderr.write(f'❌ No se encontró {json_path}')
            return

        with open(json_path, 'r') as f:
            lotes_data = json.load(f)

        self.stdout.write(f'Lotes en JSON: {len(lotes_data)}')

        # Borrar lotes anteriores
        borrados, _ = Lote.objects.filter(plano=plano).delete()
        self.stdout.write(f'Lotes anteriores eliminados: {borrados}')

        # Crear nuevos lotes
        creados = 0
        for ld in lotes_data:
            Lote.objects.create(
                plano=plano,
                puntos=ld['puntos'],
                estado='disponible',
            )
            creados += 1

        self.stdout.write(self.style.SUCCESS(f'✅ {creados} lotes importados correctamente.'))
