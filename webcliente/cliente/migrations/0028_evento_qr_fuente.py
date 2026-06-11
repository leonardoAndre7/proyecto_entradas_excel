from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0027_evento_qr_config'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evento',
            name='qr_color_fondo',
            field=models.CharField(default='#ffffff', max_length=20, verbose_name='QR Color fondo'),
        ),
        migrations.AddField(
            model_name='evento',
            name='qr_fuente',
            field=models.CharField(default='Roboto-Bold.ttf', max_length=50, verbose_name='Fuente del nombre'),
        ),
    ]
