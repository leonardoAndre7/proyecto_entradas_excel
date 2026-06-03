from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lotes', '0004_lote_puntos_alter_lote_height_alter_lote_width_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plano',
            name='imagen',
            field=models.FileField(
                upload_to='planos/',
                help_text='Sube la imagen del plano (PNG, JPG) o un archivo PDF.'
            ),
        ),
    ]
