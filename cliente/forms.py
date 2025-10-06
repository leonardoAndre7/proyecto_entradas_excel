from django import forms
from .models import Participante

class ParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        exclude = ['cod_cliente', 'precio', 'total_pagar', 'qr']
        
