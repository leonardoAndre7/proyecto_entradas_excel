from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0036_pagos_en_partes'),
    ]

    operations = [
        migrations.AddField(
            model_name='participante',
            name='whatsapp_enviado',
            field=models.BooleanField(default=False),
        ),
    ]
