from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cliente", "0030_restaurar_fondos_evento"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarifa",
            name="dias_validos",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="Días de acceso (ingresos permitidos)"),
        ),
        migrations.AddField(
            model_name="tarifa",
            name="hora_desde",
            field=models.TimeField(blank=True, null=True, verbose_name="Ingreso permitido desde"),
        ),
        migrations.AddField(
            model_name="tarifa",
            name="hora_hasta",
            field=models.TimeField(blank=True, null=True, verbose_name="Ingreso permitido hasta"),
        ),
        migrations.CreateModel(
            name="IngresoParticipante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_hora", models.DateTimeField()),
                (
                    "participante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingresos",
                        to="cliente.participante",
                    ),
                ),
            ],
            options={"ordering": ["fecha_hora"]},
        ),
    ]
