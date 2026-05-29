from django.contrib import admin
from django.utils.html import format_html
from .models import Participante, EmailEnviado

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('cod_cliente', 'nombres', 'apellidos', 'dni', 'tipo_entrada', 'cantidad', 'total_pagar')
    search_fields = ('cod_cliente', 'nombres', 'apellidos', 'dni')



@admin.register(EmailEnviado)
class EmailEnviadoAdmin(admin.ModelAdmin):
    list_display = ("destinatario", "asunto", "enviado", "fecha_envio")
    list_filter = ("enviado", "fecha_envio")
    search_fields = ("destinatario", "asunto")
    ordering = ("-fecha_envio",)

    readonly_fields = ("preview_html", "preview_adjunto")

    def preview_html(self, obj):
        return format_html(obj.cuerpo_html)

    preview_html.short_description = "Contenido del correo"

    def preview_adjunto(self, obj):
        if obj.adjunto:
            return format_html(
                '<img src="{}" style="max-width: 100%; border:1px solid #ccc;">',
                obj.adjunto.url
            )
        return "Sin adjunto"

    preview_adjunto.short_description = "Adjunto enviado"