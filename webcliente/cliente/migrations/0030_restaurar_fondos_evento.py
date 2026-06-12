import os
from django.conf import settings
from django.db import migrations

# Los fondos de boleto ahora viajan dentro del repo (webcliente/media/event_backgrounds/).
# Si el archivo al que apunta Evento.imagen_fondo se perdió (Render borra el disco
# en cada deploy), se busca un archivo con el mismo nombre base en la copia del repo.


def restaurar_fondos(apps, schema_editor):
    Evento = apps.get_model("cliente", "Evento")
    carpeta_repo = os.path.join(settings.MEDIA_ROOT, "event_backgrounds")
    if not os.path.isdir(carpeta_repo):
        return
    disponibles = {f.lower(): f for f in os.listdir(carpeta_repo)}
    if not disponibles:
        return

    for evento in Evento.objects.exclude(imagen_fondo=""):
        if not evento.imagen_fondo:
            continue
        actual = os.path.join(settings.MEDIA_ROOT, evento.imagen_fondo.name)
        if os.path.exists(actual):
            continue
        base = os.path.basename(evento.imagen_fondo.name).lower()
        candidato = disponibles.get(base)
        if not candidato:
            # Django agrega sufijos aleatorios al repetir nombre (foto_Ab12Cd3.png):
            # probar con el nombre sin el último sufijo _XXXXXXX
            nombre, ext = os.path.splitext(base)
            if "_" in nombre:
                sin_sufijo = nombre.rsplit("_", 1)[0] + ext
                candidato = disponibles.get(sin_sufijo)
        if candidato:
            evento.imagen_fondo.name = "event_backgrounds/" + candidato
            evento.save(update_fields=["imagen_fondo"])


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0029_participante_email_enviado"),
    ]

    operations = [
        migrations.RunPython(restaurar_fondos, migrations.RunPython.noop),
    ]
