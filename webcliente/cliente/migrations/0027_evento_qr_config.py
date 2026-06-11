from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0026_alter_participante_tarifa'),
    ]

    operations = [
        migrations.AddField(
            model_name='evento',
            name='qr_pos_x',
            field=models.IntegerField(default=168, verbose_name='QR Posición X (px)'),
        ),
        migrations.AddField(
            model_name='evento',
            name='qr_pos_y',
            field=models.IntegerField(default=405, verbose_name='QR Posición Y (px)'),
        ),
        migrations.AddField(
            model_name='evento',
            name='qr_ancho',
            field=models.IntegerField(default=567, verbose_name='QR Ancho (px)'),
        ),
        migrations.AddField(
            model_name='evento',
            name='qr_alto',
            field=models.IntegerField(default=569, verbose_name='QR Alto (px)'),
        ),
        migrations.AddField(
            model_name='evento',
            name='qr_color_frente',
            field=models.CharField(default='#000000', max_length=7, verbose_name='QR Color frente'),
        ),
        migrations.AddField(
            model_name='evento',
            name='qr_color_fondo',
            field=models.CharField(default='#ffffff', max_length=7, verbose_name='QR Color fondo'),
        ),
    ]
