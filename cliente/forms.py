# forms.py
from django import forms
from .models import Participante

class ParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        fields = ['nombres', 'apellidos', 'dni', 'celular', 'correo', 'tipo_entrada', 'cantidad', 'vendedor']
