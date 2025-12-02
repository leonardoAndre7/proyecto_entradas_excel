# forms.py
from django import forms
from .models import Participante,Voucher, Previaparticipantes


class ParticipanteForm(forms.ModelForm):
    csv_file = forms.FileField(required=False, help_text="Sube un CSV para carga masiva")

    class Meta:
        model = Previaparticipantes
        fields = ['nombres', 'dni', 'celular']  # campos normales


class ParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        fields = ['nombres', 'apellidos', 'dni', 'celular', 'correo', 'tipo_entrada', 'cantidad', 'vendedor']



class ExcelUploadForm(forms.Form):
    archivo = forms.FileField(
        label="Seleccionar archivo Excel",
        widget=forms.ClearableFileInput(attrs={'accept': '.xlsx,.xls'})
    )
    

class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = ['imagen']