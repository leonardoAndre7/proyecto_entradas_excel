from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0028_evento_qr_fuente'),
    ]

    operations = [
        migrations.AddField(
            model_name='participante',
            name='email_enviado',
            field=models.BooleanField(default=False),
        ),
    ]
