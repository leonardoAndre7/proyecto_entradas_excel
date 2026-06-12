import json
import os
from decimal import Decimal
from django.db import migrations

# Restauración de emergencia: si la BD no tiene ningún Plano (p. ej. se borró
# por accidente — al borrar un Plano los Lotes caen en cascada), se recrea el
# plano Paraiso Frutal y sus 428 lotes desde el respaldo versionado en el repo.
# Si ya existe al menos un Plano, no toca nada.
FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "lotes_respaldo.json")


def restaurar_lotes(apps, schema_editor):
    Plano = apps.get_model("lotes", "Plano")
    Lote = apps.get_model("lotes", "Lote")

    if Plano.objects.exists():
        return

    ruta = os.path.abspath(FIXTURE)
    if not os.path.exists(ruta):
        return

    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)

    plano = Plano.objects.create(
        nombre=data["plano"]["nombre"],
        imagen=data["plano"]["imagen"],
    )
    lotes = [
        Lote(
            plano=plano,
            numero=ld["numero"],
            puntos=ld["puntos"],
            x=ld["x"], y=ld["y"], width=ld["width"], height=ld["height"],
            estado=ld["estado"],
            precio=Decimal(ld["precio"]) if ld["precio"] is not None else None,
        )
        for ld in data["lotes"]
    ]
    Lote.objects.bulk_create(lotes)


class Migration(migrations.Migration):

    dependencies = [
        ("lotes", "0011_restaurar_imagen_plano"),
    ]

    operations = [
        migrations.RunPython(restaurar_lotes, migrations.RunPython.noop),
    ]
