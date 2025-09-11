from django.views.generic import CreateView, UpdateView, DeleteView, ListView
from .models import Participante,RegistroCorreo
import pandas as pd
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.core.mail import EmailMessage
from django.conf import settings
from .utils import enviar_correo_participante, enviar_correo_participante
from django.db.models import Q


def confirmar_pago(request, pk):
    # Obtener el participante
    participante = get_object_or_404(Participante, pk=pk)
    
    # Marcar como pagado
    participante.pago_confirmado = True
    participante.save()
    
    # Enviar correo de confirmación
    enviar_correo_participante(participante)
    
    # Redirigir a la lista de participantes
    return redirect('participante_lista')

from django.db import models

def enviar_correo_participante(participante):
    """
    Envía dos correos:
    1. Con el QR adjunto como entrada
    2. Confirmación del tipo de entrada adquirida
    """
    # 🔹 Primer correo con el QR adjunto
    asunto1 = "🎟️ Tu entrada al evento"
    mensaje1 = f"Hola {participante.nombres},\n\nAdjunto encontrarás tu entrada con el código QR."
    email1 = EmailMessage(
        asunto1,
        mensaje1,
        settings.DEFAULT_FROM_EMAIL,
        [participante.correo],
    )
    if participante.qr:
        email1.attach_file(participante.qr.path)  # Adjuntar QR
    email1.send(fail_silently=False)

    # Registrar el primer correo
    RegistroCorreo.objects.create(
        participante=participante,
        enviado=True,
        mensaje="Correo con QR enviado."
    )

    # 🔹 Segundo correo con el tipo de entrada
    asunto2 = "✅ Confirmación de tu compra"
    mensaje2 = (
        f"Hola {participante.nombres},\n\n"
        f"Has adquirido la entrada: {participante.tipo_entrada}\n"
        f"Cantidad: {participante.cantidad}\n"
        f"Total pagado: {participante.total_pagar}\n\n"
        "¡Gracias por tu compra!"
    )
    email2 = EmailMessage(
        asunto2,
        mensaje2,
        settings.DEFAULT_FROM_EMAIL,
        [participante.correo],
    )
    email2.send(fail_silently=False)

    # Registrar el segundo correo
    RegistroCorreo.objects.create(
        participante=participante,
        enviado=True,
        mensaje="Correo de confirmación enviado."
    )


class ParticipanteCreateView(CreateView):
    model = Participante
    fields = ['nombres','apellidos','dni','celular','correo','tipo_entrada','cantidad']
    template_name = 'cliente/participante_form.html'
    success_url = reverse_lazy('participante_lista')


class ParticipanteUpdateView(UpdateView):
    model = Participante
    fields = ['nombres','apellidos','dni','celular','correo','tipo_entrada','cantidad','precio']
    template_name = 'cliente/participante_form.html'
    success_url = reverse_lazy('participante_lista')

class ParticipanteDeleteView(DeleteView):
    model = Participante
    template_name = 'cliente/participante_confirm_delete.html'
    success_url = reverse_lazy('participante_lista')
 
class ParticipanteListView(ListView):
    model = Participante
    template_name = 'cliente/lista.html'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")  # Obtiene el valor del input de búsqueda
        if q:
            queryset = queryset.filter(
                Q(nombres__icontains=q) | Q(dni__icontains=q)
            )
        return queryset

def mostrar_qr(request, pk):
    participante = get_object_or_404(Participante, pk=pk)
    return render(request, "cliente/mostrar_qr.html", {"participante": participante})

def exportar_excel(request):
    participantes = Participante.objects.all().values()
    df = pd.DataFrame(participantes)

    # Crear la respuesta HTTP con el archivo Excel
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=participantes.xlsx'
    df.to_excel(response, index=False)
    return response

def panel_control(request):
    registros = RegistroCorreo.objects.all().order_by('-fecha_envio')
    return render(request, 'cliente/panel_control.html', {'registros': registros})

def reenviar_correo(request, pk):
    registro = RegistroCorreo.objects.get(pk=pk)
    participante = registro.participante
    enviar_correo_participante(participante)
    return redirect('panel_control')