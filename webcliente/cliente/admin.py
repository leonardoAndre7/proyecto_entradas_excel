from django.contrib import admin
from .models import Participante, EmailEnviado

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('cod_cliente', 'nombres', 'apellidos', 'dni', 'tipo_entrada', 'cantidad', 'total_pagar')
    search_fields = ('cod_cliente', 'nombres', 'apellidos', 'dni')


@admin.register(EmailEnviado)
class EmailEnviadoAdmin(admin.ModelAdmin):
    list_display = (
        "destinatario",
        "asunto",
        "enviado",
        "fecha_envio",
    )
    list_filter = ("enviado", "fecha_envio")
    search_fields = ("destinatario", "asunto")
    ordering = ("-fecha_envio",)