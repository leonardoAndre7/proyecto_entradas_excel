import os
from django.conf import settings
from django.db import migrations

# La imagen del plano ahora viaja dentro del repo (webcliente/media/planos/).
# Render borra el disco en cada deploy; si el archivo al que apunta el registro
# Plano ya no existe, lo re-apuntamos a la copia incluida en el repositorio.
IMAGEN_REPO = "planos/PLANO_PARAISO_FRUTAL.png"


def restaurar_imagen(apps, schema_editor):
    Plano = apps.get_model("lotes", "Plano")
    repo_path = os.path.join(settings.MEDIA_ROOT, IMAGEN_REPO)
    if not os.path.exists(repo_path):
        return
    for plano in Plano.objects.all():
        actual = os.path.join(settings.MEDIA_ROOT, plano.imagen.name) if plano.imagen else None
        if not actual or not os.path.exists(actual):
            plano.imagen.name = IMAGEN_REPO
            plano.save(update_fields=["imagen"])


class Migration(migrations.Migration):

    dependencies = [
        ("lotes", "0010_lote_numero"),
    ]

    operations = [
        migrations.RunPython(restaurar_imagen, migrations.RunPython.noop),
    ]
