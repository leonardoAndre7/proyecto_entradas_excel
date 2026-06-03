from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0025_perfilusuario_google_oauth2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participante',
            name='tarifa',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='participantes',
                to='cliente.tarifa',
            ),
        ),
    ]
