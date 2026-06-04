# Generated manually — añade el estado "bloqueado" a Lote.estado

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lotes', '0005_alter_plano_imagen_filefield'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lote',
            name='estado',
            field=models.CharField(
                choices=[
                    ('disponible', 'Disponible'),
                    ('vendido', 'Vendido'),
                    ('reservado', 'Reservado'),
                    ('bloqueado', 'Bloqueado'),
                ],
                default='disponible',
                max_length=20,
            ),
        ),
    ]
