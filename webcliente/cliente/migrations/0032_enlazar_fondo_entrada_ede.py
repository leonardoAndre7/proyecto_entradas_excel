import os
from django.conf import settings
from django.db import migrations

# Render borra el disco en cada deploy y con él las imágenes subidas desde el panel.
# La plantilla de la entrada de "El Despertar del Emprendedor 2026" viaja ahora dentro del
# repo (media/event_backgrounds/entrada_ede_2026.png). Esta migración solo toca eventos
# cuyo fondo apunta a un archivo que ya no existe; no modifica los que sí lo tienen.

PLANTILLA = "event_backgrounds/entrada_ede_2026.png"


def enlazar_fondo(apps, schema_editor):
    Evento = apps.get_model("cliente", "Evento")
    ruta_repo = os.path.join(settings.MEDIA_ROOT, PLANTILLA)
    if not os.path.exists(ruta_repo):
        return

    for evento in Evento.objects.exclude(imagen_fondo=""):
        if not evento.imagen_fondo:
            continue
        actual = os.path.join(settings.MEDIA_ROOT, evento.imagen_fondo.name)
        if os.path.exists(actual):
            continue
        if "despertar" in (evento.nombre or "").lower():
            evento.imagen_fondo.name = PLANTILLA
            evento.save(update_fields=["imagen_fondo"])


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0031_tarifa_dias_horario_ingresoparticipante"),
    ]

    operations = [
        migrations.RunPython(enlazar_fondo, migrations.RunPython.noop),
    ]
