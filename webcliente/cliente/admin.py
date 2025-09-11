from django.contrib import admin
from .models import Participante

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('cod_cliente', 'nombres', 'apellidos', 'dni', 'tipo_entrada', 'cantidad', 'total_pagar')
    search_fields = ('cod_cliente', 'nombres', 'apellidos', 'dni')
