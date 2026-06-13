import os
from django.conf import settings
from django.db import migrations

# Render borra el disco en cada deploy. Si el Plano apunta a un archivo con
# sufijo aleatorio (ej: _5y3PEdR) que ya no existe, lo re-apuntamos a la
# copia canónica incluida en el repositorio.
IMAGEN_REPO = "planos/PLANO_PARAISO_FRUTAL.png"


def restaurar_imagen_v2(apps, schema_editor):
    Plano = apps.get_model("lotes", "Plano")
    repo_path = os.path.join(settings.MEDIA_ROOT, IMAGEN_REPO)
    if not os.path.exists(repo_path):
        return  # el PNG del repo tampoco está — nada que hacer
    for plano in Plano.objects.all():
        if not plano.imagen:
            plano.imagen.name = IMAGEN_REPO
            plano.save(update_fields=["imagen"])
            continue
        actual = os.path.join(settings.MEDIA_ROOT, plano.imagen.name)
        if not os.path.exists(actual):
            plano.imagen.name = IMAGEN_REPO
            plano.save(update_fields=["imagen"])


class Migration(migrations.Migration):

    dependencies = [
        ("lotes", "0012_restaurar_lotes"),
    ]

    operations = [
        migrations.RunPython(restaurar_imagen_v2, migrations.RunPython.noop),
    ]
