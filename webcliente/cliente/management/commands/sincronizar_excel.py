import pandas as pd
from django.core.management.base import BaseCommand
from cliente.models import Participante

class Command(BaseCommand):
    help = "Sincroniza los datos del Excel con la base de datos"

    def handle(self, *args, **options):
        archivo_excel = "cliente/data/cliente.xlsx"

        # Leer Excel
        df = pd.read_excel(archivo_excel, header=0)

        # Imprimir los nombres de columna tal como Pandas los lee
        print(df.columns.tolist())
        # Limpiar espacios en los nombres de columnas y pasar a mayúsculas
        df.columns = df.columns.str.strip().str.upper()

        # Mapeo de columnas esperado
        columnas = {
            'DNI': 'DNI',
            'COD_CLIENTE': 'COD_CLIENTE',
            'NOMBRES': 'NOMBRES',
            'APELLIDOS': 'APELLIDOS',
            'CELULAR': 'CELULAR',
            'CORREO': 'CORREO',
            'TIPO_ENTRADA': 'TIPO_ENTRADA',
            'CANTIDAD': 'CANTIDAD',
            'PRECIO': 'PRECIO',
            'TOTAL_PAGAR': 'TOTAL_PAGAR',
        }

        # Verificar que todas las columnas existan
        for col in columnas:
            if col not in df.columns:
                self.stdout.write(self.style.ERROR(f"Columna '{col}' no encontrada en el Excel"))
                return

        # Recorrer filas y crear/actualizar participantes
        for _, fila in df.iterrows():
            Participante.objects.update_or_create(
                    dni=str(fila[columnas['DNI']]),
                    defaults={
                        'nombres': fila[columnas['NOMBRES']],
                        'apellidos': fila[columnas['APELLIDOS']],
                        'celular': str(fila[columnas['CELULAR']]),
                        'correo': fila[columnas['CORREO']],
                        'cod_cliente': fila[columnas['COD_CLIENTE']],
                        'tipo_entrada': fila[columnas['TIPO_ENTRADA']],
                        'cantidad': int(fila[columnas['CANTIDAD']]),
                        'precio': float(fila[columnas['PRECIO']]),
                        'total_pagar': float(fila[columnas['TOTAL_PAGAR']]),
                    }
                )

        self.stdout.write(self.style.SUCCESS("Excel sincronizado correctamente."))
