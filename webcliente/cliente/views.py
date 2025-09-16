from django.views.generic import CreateView, UpdateView, DeleteView, ListView
from .models import Participante,RegistroCorreo
import pandas as pd
import openpyxl
import qrcode
from django.urls import reverse
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from PIL import Image, ImageDraw, ImageFont
from django.core.mail import EmailMessage
from django.conf import settings
from .utils import enviar_correo_participante
from django.db.models import Q
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import os

def confirmar_pago(request, pk):
    participante = get_object_or_404(Participante, pk=pk)

    # Confirmar pago
    participante.pago_confirmado = True
    participante.save()

    # Enviar correo
    enviar_correo_participante(participante)

    # Crear o actualizar registro de correo
    registro, created = RegistroCorreo.objects.get_or_create(
        participante=participante,
        defaults={"enviado": True, "fecha_envio": timezone.now()}
    )

    if not created:
        registro.enviado = True
        registro.fecha_envio = timezone.now()
        registro.save()

    return redirect("participante_lista")


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

def generar_qr(request, pk):
    participante = get_object_or_404(Participante, pk=pk)

    # Construir la URL que se abrirá al escanear
    url = request.build_absolute_uri(
        reverse("validar_entrada", args=[participante.pk])
    )

    # 👇 Esto te lo mostrará en consola al momento de generar el QR
    print("👉 URL del QR generado:", url)

    # Crear el QR con esa URL
    qr = qrcode.make(url)

    response = HttpResponse(content_type="image/png")
    qr.save(response, "PNG")
    return response


def mostrar_qr(request, pk):
    participante = get_object_or_404(Participante, pk=pk)

    # Ruta de la imagen de fondo
    fondo_path = os.path.join(settings.BASE_DIR, 'cliente', 'static', 'cliente', 'img', 'exponentes.png')
    img = Image.open(fondo_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Escribir los datos encima
    font = ImageFont.truetype("arial.ttf", 24)
    draw.text((20, 50), f"Código: {participante.cod_cliente}", fill="black", font=font)
    draw.text((20, 100), f"DNI: {participante.dni}", fill="black", font=font)

    # Respuesta como imagen
    response = HttpResponse(content_type="image/png")
    img.save(response, "PNG")
    return response

def validar_entrada(request, pk):
    participante = get_object_or_404(Participante, pk=pk)

    if not participante.usado:
        participante.usado = True
        participante.save()
        return render(request, "cliente/entrada_valida.html", {"participante": participante})
    else:
        return render(request, "cliente/entrada_usada.html", {"participante": participante})


def marcar_ingreso(request, pk):
    participante = get_object_or_404(Participante, pk=pk)
    if not participante.entrada_usada:  # solo marcar si aún no entró
        participante.entrada_usada = True
        participante.save()
    return redirect('lista')  # Ajusta al nombre de tu lista

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
    registro = get_object_or_404(RegistroCorreo, pk=pk)
    participante = registro.participante

    # Reenviar correo
    enviar_correo_participante(participante)

    # Actualizar registro
    registro.enviado = True
    registro.fecha_envio = timezone.now()
    registro.save()

    return redirect("panel_control")

def exportar_excel_control(request):
    registros = RegistroCorreo.objects.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Registros"

    # Encabezados
    columnas = ["Nombres", "Correo", "Tipo Entrada", "Fecha Envío", "Enviado"]
    ws.append(columnas)

    # Datos
    for r in registros:
        ws.append([
            f"{r.participante.nombres} {r.participante.apellidos}",
            r.participante.correo,
            r.participante.tipo_entrada,
            r.fecha_envio.strftime("%d/%m/%Y %H:%M") if r.fecha_envio else "",
            "Sí" if r.enviado else "No"
        ])

    # Respuesta HTTP con archivo
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="control.xlsx"'
    wb.save(response)
    return response

def registros_json(request):
    registros = RegistroCorreo.objects.select_related("participante").order_by("-fecha_envio")
    data = {
        "registros": [
            {
                "id": r.id,
                "nombre": f"{r.participante.nombres} {r.participante.apellidos}",
                "correo": r.participante.correo,
                "entrada": r.participante.tipo_entrada,
                "fecha": r.fecha_envio.strftime("%d/%m/%Y") if r.fecha_envio else "",
                "estado": r.enviado,
            }
            for r in registros
        ]
    }
    return JsonResponse(data)

def exportar_pdf_control(request):
    registros = RegistroCorreo.objects.all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Encabezado
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Reporte de Registros", styles["Heading1"]))

    # Tabla
    data = [["Nombres", "Correo", "Tipo Entrada", "Fecha Envío", "Enviado"]]
    for r in registros:
        data.append([
            f"{r.participante.nombres} {r.participante.apellidos}",
            r.participante.correo,
            r.participante.tipo_entrada,
            r.fecha_envio.strftime("%d/%m/%Y") if r.fecha_envio else "",
            "Sí" if r.enviado else "No"
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.gray),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(table)

    # Generar PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="control.pdf"'
    response.write(pdf)
    return response