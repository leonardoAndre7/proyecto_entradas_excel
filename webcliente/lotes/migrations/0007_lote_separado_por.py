# Añade el campo separado_por a Lote (quién reservó el lote).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lotes', '0006_alter_lote_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='lote',
            name='separado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lotes_separados',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
