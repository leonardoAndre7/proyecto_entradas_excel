from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cliente', '0024_evento_aforo_maximo_evento_limite_entradas_persona'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='google_email',
            field=models.EmailField(blank=True, null=True, verbose_name='Gmail Conectado (OAuth2)'),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='google_refresh_token',
            field=models.TextField(blank=True, null=True, verbose_name='Google Refresh Token'),
        ),
    ]
