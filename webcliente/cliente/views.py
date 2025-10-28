from django.views.generic import CreateView, UpdateView, DeleteView, ListView
from .models import Participante, Voucher,RegistroCorreo, Previaparticipantes
import pandas as pd
import openpyxl
import qrcode
from django.db.models import Max
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from django.urls import reverse
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from PIL import Image, ImageDraw, ImageFont
from django.core.mail import EmailMessage
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from .utils import enviar_correo_participante
from django.db.models import Q
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import os
from django.contrib.staticfiles import finders
import socket
from twilio.rest import Client
from io import BytesIO
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from email.mime.image import MIMEImage
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
import qrcode
import base64
import os
import tempfile
import requests
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .forms import ParticipanteForm
from .forms import ExcelUploadForm
####################################################
###### PREVIA DEL DESPERTAR 
##########################################
#############################################
##############################################
#import pywhatkit
from django.shortcuts import render, redirect
from .models import Previaparticipantes
import csv
from django.contrib import messages
import openpyxl
from django.contrib import messages
from django.contrib.auth.models import User


def enviar_masivo(request):
    participantes = Participante.objects.filter()

    if not participantes.exists():
        messages.warning(request, "⚠️ No hay participantes registrados.")
        return redirect("participante_lista")

    enviados = 0
    errores = 0

    for participante in participantes:
        try:
            # ✅ Enviar solo si tiene ambos checks activados
            if not (participante.validado_admin and participante.validado_contabilidad):
                print(f"⏭️ Saltando {participante.nombres}: faltan validaciones (Admin o Contabilidad)")
                continue

            print(f"📤 Enviando a {participante.nombres} ({participante.correo})")
            print(f"! Paquete recibido: {participante.tipo_entrada}")

            # Generar QR
            url = f"https://proyecto-entradas-excel-1.onrender.com/validar/{participante.token}/"
            qr_img = qrcode.make(url).convert("RGB")

            # Crear imagen personalizada
            imagen_final = generar_imagen_personalizada(
                nombre_cliente=participante.nombres,
                paquete=participante.tipo_entrada,
                qr_img=qr_img
            )

            if imagen_final is None:
                print(f"⚠️ No se pudo generar imagen para {participante.nombres}")
                errores += 1
                continue

            buffer = BytesIO()
            imagen_final.save(buffer, format='PNG')
            buffer.seek(0)

            # Subir a ImgBB
            api_key = settings.IMGBB_API_KEY
            encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": api_key, "image": encoded_image},
                timeout=20
            )
            image_url = response.json().get("data", {}).get("url") if response.status_code == 200 else None

            # Enviar correo
            asunto = "🎟️ Tu entrada - El Despertar del Emprendedor"
            html_mensaje = f"""
            <html>
            <body>
                <p>Hola {participante.nombres},</p>
                <p>Tienes {participante.cantidad} Entradas para el Evento </p>
                <p>Gracias por tu compra. Adjunto tu entrada personalizada.</p>
                <p>¡Nos vemos pronto!</p>
                <img src="cid:entrada" style="max-width:100%; height:auto;">
            </body>
            </html>
            """
            email = EmailMultiAlternatives(
                subject=asunto,
                body="Tu correo no soporta HTML",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[participante.correo],
            )
            email.attach_alternative(html_mensaje, "text/html")
            img = MIMEImage(buffer.getvalue())
            img.add_header('Content-ID', '<entrada>')
            img.add_header('Content-Disposition', 'inline', filename='entrada.png')
            email.attach(img)
            email.send()
            
            try:
            # Enviar WhatsApp con Twilio
                account_sid = settings.TWILIO_ACCOUNT_SID
                auth_token = settings.TWILIO_AUTH_TOKEN
                client = Client(account_sid, auth_token)

                numero_destino = f"whatsapp:+51{''.join(filter(str.isdigit, participante.celular))}"
                numero_twilio = settings.TWILIO_PHONE_NUMBER

                if image_url:
                    # ✅ Mensaje con imagen
                    mensaje_whatsapp = (
                        f"🎟️ *Confirmación de tu entrada - El Despertar del Emprendedor*\n\n"
                        f"¡Hola {participante.nombres}! 👋\n\n"
                        f"Tienes {participante.cantidad} Entradas para el Evento \n\n"
                        f"Gracias por tu compra. Adjunto encontrarás tu *entrada personalizada* "
                        f"para el evento *El Despertar del Emprendedor*.\n\n"
                        f"📱 Únete al grupo oficial del evento:\n"
                        f"https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT\n\n"
                        f"Guarda esta imagen y muéstrala el día del evento. 📅\n"
                        f"¡Nos vemos pronto! 🙌"
                    )

                    client.messages.create(
                        from_=numero_twilio,
                        to=numero_destino,
                        body=mensaje_whatsapp,
                        media_url=[image_url]
                    )
                    print(f"✅ WhatsApp enviado a {participante.nombres} ({numero_destino}) con imagen.")

                else:
                    # ✅ Mensaje solo texto (sin imagen)
                    mensaje_whatsapp = (
                        f"🎟️ *Confirmación de tu entrada - El Despertar del Emprendedor*\n\n"
                        f"¡Hola {participante.nombres}! 👋\n\n"
                        f"Gracias por tu compra. 🎟️ Tu entrada está registrada correctamente.\n\n"
                        f"📱 Únete al grupo oficial del evento:\n"
                        f"https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT\n\n"
                        f"¡Nos vemos pronto! 🙌"
                    )

                    client.messages.create(
                        from_=numero_twilio,
                        to=numero_destino,
                        body=mensaje_whatsapp
                    )
                    print(f"✅ WhatsApp enviado a {participante.nombres} ({numero_destino}) sin imagen.")
            
            except Exception as e:
                print(f"❌ Error al enviar WhatsApp a {participante.nombres}: {e}")


            # Registrar envío
            RegistroCorreo.objects.update_or_create(
                participante=participante,
                defaults={"enviado": True, "fecha_envio": timezone.now()}
            )

            # Marcar como enviado/pago confirmado
            participante.pago_confirmado = True
            participante.save()

            enviados += 1

        except Exception as e:
            errores += 1
            print(f"❌ Error con {participante.nombres}: {e}")

    print(f"✅ Enviados: {enviados} | ❌ Errores: {errores}")
    messages.success(request, f"✅ Se enviaron {enviados} entradas correctamente. ({errores} errores)")
    return redirect("participante_lista")




def registro_participante(request):
    # Generar el nuevo código automáticamente
    ultimo = Previaparticipantes.objects.order_by('-id').first()
    if ultimo and ultimo.cod_part.startswith('PART'):
        numero = int(ultimo.cod_part.replace('PART', '')) + 1
    else:
        numero = 1
    nuevo_cod = f"PART{numero:03d}"

    if request.method == 'POST':
        # 1️⃣ Carga masiva desde Excel
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            wb = openpyxl.load_workbook(excel_file)
            sheet = wb.active

            # Suponiendo que la primera fila es encabezado: Nombres, DNI, Celular, Asesor
            for row in sheet.iter_rows(min_row=2, values_only=True):
                nombres, dni, celular, asesor = row[:4]

                # Generar nuevo código
                ultimo = Previaparticipantes.objects.order_by('-id').first()
                numero = int(ultimo.cod_part.replace('PART', '')) + 1 if ultimo else 1
                nuevo_cod_row = f"PART{numero:03d}"

                Previaparticipantes.objects.create(
                    cod_part=nuevo_cod_row,
                    nombres=nombres,
                    dni=dni,
                    celular=celular,
                    asesor=asesor
                )

            messages.success(request, "Participantes cargados desde Excel correctamente.")

        else:
            # 2️⃣ Registro individual
            participante = Previaparticipantes.objects.create(
                cod_part=nuevo_cod,
                nombres=request.POST.get('nombres'),
                dni=request.POST.get('dni'),
                celular=request.POST.get('celular'),
                asesor=request.POST.get('asesor')
            )

            # Guardar vouchers
            for archivo in request.FILES.getlist('vouchers'):
                Voucher.objects.create(participante=participante, imagen=archivo)

            messages.success(request, f"Participante {participante.nombres} registrado correctamente.")

        return redirect('registro_participante')

    # Mostrar todos los participantes
    participantes = Previaparticipantes.objects.prefetch_related('vouchers').all()
    return render(request, 'cliente/registro_participante.html', {
        'nuevo_cod': nuevo_cod,
        'participantes': participantes
    })




def actualizar_participante_previa(request, pk):
    participante = get_object_or_404(Previaparticipantes, pk=pk)

    if request.method == 'POST':
        participante.nombres = request.POST.get('nombres')
        participante.dni = request.POST.get('dni')
        participante.celular = request.POST.get('celular')
        participante.asesor = request.POST.get('asesor')
        participante.validado_contabilidad = 'validado_contabilidad' in request.POST
        participante.validado_administracion = 'validado_administracion' in request.POST
    
        
        participante.save()

        # Subir nuevos vouchers si hay
        for archivo in request.FILES.getlist('vouchers'):
            Voucher.objects.create(participante=participante, imagen=archivo)

        return redirect('registro_participante')  # 🔹 Volvemos a la página principal

    return render(request, 'cliente/actualizar_participante_previo.html', {
        'participante': participante
    })



def eliminar_participante_previa(request, pk):
    participante = get_object_or_404(Previaparticipantes, pk=pk)
    if request.method == "POST":
        participante.delete()
        return redirect('registro_participante') 





def enviar_whatsapp_qr(request, cod_part):
    # Obtener participante correcto
    participante = get_object_or_404(Previaparticipantes, cod_part=cod_part)

    if not participante.qr_image:
        messages.error(request, "❌ El participante no tiene QR generado.")
        return redirect("registro_participante")

    qr_path = participante.qr_image.path

    try:
        # Abrir imagen
        img = Image.open(qr_path)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.thumbnail((1080, 1440))

        # Guardar imagen temporal
        tmp_path = os.path.join(tempfile.gettempdir(), f"entrada_{participante.id}.jpg")
        img.save(tmp_path, format="JPEG", quality=95)

    except Exception as e:
        messages.error(request, f"❌ Error al procesar la imagen: {e}")
        return redirect("registro_participante")

    try:
        # Configurar Twilio
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        client = Client(account_sid, auth_token)

        numero_twilio = f"whatsapp:{settings.TWILIO_PHONE_NUMBER}"
        numero_destino = f"whatsapp:+51{''.join(filter(str.isdigit, participante.celular or ''))}"

        mensaje_texto = (
            f"🎟️ Hola {participante.nombres}, tu entrada para El Despertar del Emprendedor está lista.\n"
            "¡Nos vemos pronto! 🙌"
        )

        # Subir imagen a ImgBB para obtener URL pública
        with open(tmp_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": settings.IMGBB_API_KEY, "image": encoded_image},
            timeout=20
        )

        if response.status_code == 200:
            image_url = response.json().get("data", {}).get("url")
            client.messages.create(
                from_=numero_twilio,
                to=numero_destino,
                body=mensaje_texto,
                media_url=[image_url]
            )
        else:
            # Solo texto si falla la subida de la imagen
            client.messages.create(
                from_=numero_twilio,
                to=numero_destino,
                body=mensaje_texto
            )

        messages.success(request, f"✅ Entrada enviada correctamente a {participante.nombres}")

    except Exception as e:
        messages.error(request, f"❌ Error enviando WhatsApp con Twilio: {e}")

    return redirect("registro_participante")


from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment


# Exportar a Excel
def exportar_excel_previo(request):
    try:
        participantes = Previaparticipantes.objects.all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Participantes"

        headers = ['Código', 'Nombre', 'DNI', 'Celular', 'Asesor', 'Validado Contabilidad', 'Validado Administración']
        for col_num, column_title in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=column_title)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='6A1B9A', end_color='6A1B9A', fill_type='solid')
            cell.alignment = Alignment(horizontal='center')

        for row_num, p in enumerate(participantes, start=2):
            ws.cell(row=row_num, column=1, value=p.cod_part)
            ws.cell(row=row_num, column=2, value=p.nombres)
            ws.cell(row=row_num, column=3, value=p.dni)
            ws.cell(row=row_num, column=4, value=p.celular)
            ws.cell(row=row_num, column=5, value=p.asesor)

            contabilidad = "Sí" if p.validado_contabilidad else "No"
            administracion = "Sí" if p.validado_administracion else "No"

            ws.cell(row=row_num, column=6, value=contabilidad)
            ws.cell(row=row_num, column=7, value=administracion)

        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 5

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=participantes.xlsx'
        wb.save(response)
        return response
    except Exception as e:
        # Esto imprimirá el error real en consola y aún devolverá algo
        print("Error exportando Excel:", e)
        return HttpResponse("Ocurrió un error al generar el Excel.")

# Exportar a PDF
def exportar_pdf_previo(request):
    participantes = Previaparticipantes.objects.all()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="participantes.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("📋 Lista de Participantes", styles['Title']))
    elements.append(Spacer(1, 12))

    # Datos de tabla
    data = [['Código', 'Nombre', 'DNI', 'Celular', 'Asesor', 'Validado Contabilidad', 'Validado Administración']]
    for p in participantes:
        contabilidad = "Sí" if p.validado_contabilidad else "No"
        administracion = "Sí" if p.validado_administracion else "No"
        data.append([
            p.cod_part,
            p.nombres,
            p.dni,
            p.celular,
            p.asesor,
            contabilidad,
            administracion
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6A1B9A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f0e0ff')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))

    elements.append(table)
    doc.build(elements)
    return response



def validar_entrada_previo(request, token):
    participante = get_object_or_404(Previaparticipantes, token=token)

    if participante.validado_administracion and participante.validado_contabilidad:
        # Ya se escaneó antes
        return render(request, "cliente/entrada_repetida.html", {"participante": participante})

    # Validación
    participante.validado_administracion = True
    participante.validado_contabilidad = True
    participante.save()

    return render(request, "cliente/entrada_validada.html", {"participante": participante})

import openpyxl
from .models import Previaparticipantes


def leer_excel(archivo):
    wb = openpyxl.load_workbook(archivo)
    hoja = wb.active
    datos = []

    # Suponiendo que la primera fila es encabezado
    encabezados = [celda.value for celda in hoja[1]]
    
    for fila in hoja.iter_rows(min_row=2, values_only=True):
        fila_dict = dict(zip(encabezados, fila))
        datos.append(fila_dict)
    
    return datos

import pandas as pd
import uuid
#import pywhatkit
import time
from django.shortcuts import redirect
from django.contrib import messages
from cliente.models import Previaparticipantes

def enviar_todos_whatsapp(request):
    if request.method != "POST":
        return redirect('registro_participante')

    participantes = Previaparticipantes.objects.exclude(celular__isnull=True).exclude(celular="")
    enviados = 0

    messages.info(request, "⏳ Enviando mensajes... no cierres el navegador ni la consola.")

    # Configurar Twilio
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    client = Client(account_sid, auth_token)
    numero_twilio = f"whatsapp:{settings.TWILIO_PHONE_NUMBER}"

    for idx, p in enumerate(participantes, start=1):
        try:
            numero = ''.join(filter(str.isdigit, str(p.celular).strip()))
            if not numero.startswith("51"):
                numero = "51" + numero
            numero_destino = f"whatsapp:+{numero}"

            mensaje_texto = f"🎟️ Hola {p.nombres}, tu entrada para El Despertar del Emprendedor está lista. ¡Gracias por registrarte!"

            # Enviar imagen si existe
            if p.qr_image:
                # Abrir y optimizar la imagen
                img = Image.open(p.qr_image.path)
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.thumbnail((1080, 1440))
                tmp_path = os.path.join(tempfile.gettempdir(), f"entrada_{p.id}.jpg")
                img.save(tmp_path, format="JPEG", quality=95)

                # Subir a ImgBB
                with open(tmp_path, "rb") as f:
                    encoded_image = base64.b64encode(f.read()).decode("utf-8")
                response = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": settings.IMGBB_API_KEY, "image": encoded_image},
                    timeout=20
                )
                image_url = response.json().get("data", {}).get("url") if response.status_code == 200 else None

                if image_url:
                    client.messages.create(
                        from_=numero_twilio,
                        to=numero_destino,
                        body=mensaje_texto,
                        media_url=[image_url]
                    )
                else:
                    # Solo texto si falla la subida de la imagen
                    client.messages.create(
                        from_=numero_twilio,
                        to=numero_destino,
                        body=mensaje_texto
                    )
            else:
                # Solo texto
                client.messages.create(
                    from_=numero_twilio,
                    to=numero_destino,
                    body=mensaje_texto
                )

            enviados += 1
            print(f"📤 [{idx}/{len(participantes)}] Enviado a {p.nombres} -> {numero}")

        except Exception as e:
            print(f"❌ Error enviando a {p.nombres}: {e}")
            continue

    messages.success(request, f"✅ Se enviaron {enviados} mensajes correctamente.")
    return redirect('registro_participante')
####################################################
#####################################################
####################################################
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            print(f"Usuario autenticado: {user.username}")

            # 👇 Redirección personalizada
            if user.username.lower() == 'admin':
                print("➡ Redirigiendo a registro_participante")
                return redirect('registro_participante')
            elif user.username.lower() == 'leo':
                print("➡ Redirigiendo a formulario_clientes")
                return redirect('formulario_clientes')
            else:
                print("➡ Usuario sin ruta definida")
                messages.error(request, 'No tienes una ruta asignada.')
                return redirect('login')

        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')


#################################################################
##############################################################3##


def index(request):
    return render(request, "cliente/index.html")

@login_required
def formulario_clientes(request):
    # Tu lógica o vista de clientes
    return render(request, "cliente/lista.html")


 

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Se conecta a un servidor público solo para obtener tu IP local
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip



from io import BytesIO
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from email.mime.image import MIMEImage
import qrcode
import os
import requests, json, base64
from django.conf import settings
from twilio.rest import Client

def confirmar_pago(request, pk):
    participante = get_object_or_404(Participante, pk=pk)

    # ✅ Confirmar pago
    participante.pago_confirmado = True
    participante.save()

    # ✅ Generar QR con dominio público
    url = f"{settings.BASE_URL}{reverse('validar_entrada', args=[participante.token])}"
    qr_img = qrcode.make(url).convert("RGB")

    # ✅ Generar imagen personalizada
    imagen_final = generar_imagen_personalizada(
        nombre_cliente=participante.nombres,
        paquete=participante.tipo_entrada,
        qr_img=qr_img
    )
    if imagen_final is None:
        messages.error(request, "❌ No se pudo generar la imagen de la entrada.")
        return redirect("participante_lista")

    # ✅ Guardar imagen
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    buffer = BytesIO()
    imagen_final.save(buffer, format='PNG')
    buffer.seek(0)

    nombre_archivo = f"entrada_{participante.id}.png"
    ruta_media = os.path.join(settings.MEDIA_ROOT, nombre_archivo)
    imagen_final.save(ruta_media, format="PNG")

    # ✅ Correo HTML
    asunto = "🎟️ Confirmación de tu entrada - El Despertar del Emprendedor"
    html_mensaje = f"""
    <html>
    <body>
        <p>Hola {participante.nombres},</p>
        <p>Tienes {participante.cantidad} Entradas para el Evento</p>
        <p>Gracias por tu compra. Adjunto encontrarás tu entrada personalizada
        para el evento <strong>El Despertar del Emprendedor</strong>.</p>
        <p>No olvides guardarla y mostrarla el día del evento.</p>
        <p>¡Nos vemos pronto!</p>
        <br>
        <img src="cid:entrada" alt="Entrada personalizada" style="max-width:100%; height:auto; display:block;">
    </body>
    </html>
    """

    email = EmailMultiAlternatives(
        subject=asunto,
        body="Tu correo no soporta HTML",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[participante.correo],
    )
    email.attach_alternative(html_mensaje, "text/html")

    img = MIMEImage(buffer.getvalue())
    img.add_header('Content-ID', '<entrada>')
    img.add_header('Content-Disposition', 'inline', filename='entrada.png')
    email.attach(img)

    try:
        email.send()
        print("✅ Correo enviado correctamente")
    except Exception as e:
        print("❌ Error enviando correo:", e)

    # ✅ Subir imagen a ImgBB
    image_url = None
    try:
        api_key = settings.IMGBB_API_KEY
        encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        response = requests.post("https://api.imgbb.com/1/upload", data={"key": api_key, "image": encoded_image})
        if response.status_code == 200:
            image_url = response.json()["data"]["url"]
            print("✅ Imagen subida correctamente:", image_url)
        else:
            print("❌ Error subiendo imagen:", response.text)
    except Exception as e:
        print("❌ Error subiendo imagen:", e)

    # ✅ Enviar WhatsApp
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        numero_twilio = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"

        numero_limpio = "".join(filter(str.isdigit, participante.celular))
        if not numero_limpio.startswith("51"):
            numero_limpio = "51" + numero_limpio
        numero_destino = f"whatsapp:+{numero_limpio}"

        mensaje_whatsapp = (
            f"¡Hola {participante.nombres}! 👋\n\n"
            f"Tienes {participante.cantidad} Entradas para el Evento 🎟️\n\n"
            f"Puedes validar tu entrada aquí:\n{url}\n\n"
            f"📱 Únete al grupo del evento:\n"
            f"https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT\n\n"
            f"Nos vemos pronto 🙌"
        )

        if image_url:
            message = client.messages.create(
            from_=numero_twilio,
            to=numero_destino,
            content_template={
                "name": "entrada_confirmada",
                "language": {"code": "es"},
                "components": [
                    {"type": "body", "parameters":[{"type":"text","text":participante.nombres}, {"type":"text","text":url}]}
                ]
            }
        )


        else:
            message = client.messages.create(from_=numero_twilio, to=numero_destino, body=mensaje_whatsapp)

        print("✅ Mensaje enviado por WhatsApp Twilio:", message.sid)
    except Exception as e:
        print("❌ Error enviando mensaje WhatsApp con Twilio:", e)

    # ✅ Registrar envío
    registro, created = RegistroCorreo.objects.get_or_create(
        participante=participante,
        defaults={"enviado": True, "fecha_envio": timezone.now()}
    )
    if not created:
        registro.enviado = True
        registro.fecha_envio = timezone.now()
        registro.save()

    messages.success(request, "✅ Pago confirmado y mensaje enviado por WhatsApp.")
    return redirect("participante_lista")


def escalar_a_a4(imagen):
    # Tamaño A4 en píxeles a 300dpi (alta resolución)
    ancho_a4 = 2480  # 8.27 pulgadas * 300dpi
    alto_a4 = 3508   # 11.69 pulgadas * 300dpi

    ancho_img, alto_img = imagen.size 

    # Escalar proporcionalmente
    factor = min(ancho_a4 / ancho_img, alto_a4 / alto_img)
    nuevo_ancho = int(ancho_img * factor)
    nuevo_alto = int(alto_img * factor)

    imagen_redimensionada = imagen.resize((nuevo_ancho, nuevo_alto), Image.ANTIALIAS)
    return imagen_redimensionada







import qrcode
from django.contrib.staticfiles import finders

def generar_imagen_personalizada(nombre_cliente, qr_img=None, paquete=None):
    """
    Genera la imagen final compuesta con textos y QR.
    Parámetros:
        nombre_cliente (str)
        paquete (str|None) : texto del paquete (ej. "FULL ACCESS"). Si es None no se dibuja.
    Retorna:
        PIL.Image
    """

    # --- Buscar las imágenes base ---
    partes = []
    for i in range(1, 8):
        ruta = finders.find(f'img/parte0{i}.jpg')
        if ruta:
            partes.append(ruta)

    if not partes:
        raise ValueError("No se encontraron imágenes para generar la entrada.")

    imagenes = []

    for p in partes:
        img = Image.open(p).convert("RGB")  # asegurar modo RGB
        filename = p.replace("\\", "/").lower()  # para comparar nombres (portable)

        # --- parte02: texto principal ---
        if 'parte02.jpg' in filename:
            draw = ImageDraw.Draw(img)
            try:
                font_black_path = finders.find('fonts/ariblk.ttf')
                font_regular_path = finders.find('fonts/arial.ttf')
                # Arial regular
                # tamaños basados en la altura para que queden proporcionados
                font_title = ImageFont.truetype(font_black_path, size=int(img.height * 0.05))
                font_name  = ImageFont.truetype(font_black_path, size=int(img.height * 0.06))
                font_body  = ImageFont.truetype(font_regular_path, size=int(img.height * 0.04))
            except Exception as e:
                print("⚠️ Error cargando fuentes:", e)
                font_title = font_name = font_body = ImageFont.load_default()

            # helper: texto con borde
            def draw_text_outline(draw_obj, pos, text, font, fill=(255,255,255), outline_fill=(0,0,0), outline_w=2):
                x, y = pos
                for dx in range(-outline_w, outline_w+1):
                    for dy in range(-outline_w, outline_w+1):
                        if dx != 0 or dy != 0:
                            draw_obj.text((x+dx, y+dy), text, font=font, fill=outline_fill)
                draw_obj.text((x, y), text, font=font, fill=fill)

            # helper: centrar texto horizontalmente
            def draw_centered(draw_obj, y, text, font, fill=(255,255,255)):
                ancho_texto = draw_obj.textlength(text, font=font)
                x = (img.width - ancho_texto) / 2
                draw_text_outline(draw_obj, (x, y), text, font, fill)

            # Título y bloque de texto
            draw_centered(draw, int(img.height * 0.085), "TU ENTRADA A EL DESPERTAR DEL EMPRENDEDOR", font_title)

            y_text = int(img.height * 0.25)
            lineas = [
                f"Hola {nombre_cliente},",
                "",
                "Gracias por unirte a EL DESPERTAR DEL EMPRENDEDOR",
                "",
                "Adjunto tu entrada personalizada:",
                "",
                "No olvides guardarla y mostrarla el",
                "     día del evento"
            ]
            for i_linea, linea in enumerate(lineas):
                if i_linea == 0:
                    draw_centered(draw, y_text, linea, font_name)
                    y_text += int(img.height * 0.09)
                else:
                    draw_centered(draw, y_text, linea, font_body)
                    y_text += int(img.height * 0.06)
    
        # --- parte03: pegar QR y texto del paquete ---
        if 'parte03.jpg' in filename:
            img = img.convert("RGB") 
            draw = ImageDraw.Draw(img)

            # Si no se pasa qr_img, generar uno por defecto
            if qr_img is None:
                url = f"https://miapp.com/validar/{nombre_cliente}"
                qr_img = qrcode.make(url).convert("RGB")


            # Coordenadas del cuadro blanco
            x1, y1, x2, y2 = 645, 218, 943, 509
            rect_w = x2 - x1
            rect_h = y2 - y1

            # margen interior
            margin = 10
            qr_size = min(rect_w, rect_h) - 2 * margin
            if qr_size <= 0:
                qr_size = max(50, int(img.width / 3))

            qr_img = qr_img.resize((qr_size, qr_size))

            # centrar QR
            qr_x = x1 + (rect_w - qr_size) // 2
            qr_y = y1 + (rect_h - qr_size) // 2
            img.paste(qr_img, (qr_x, qr_y))

            # -------------------------
            # --- Texto en la parte superior ---
            # -------------------------

            font_pkg_path = finders.find('fonts/ariblk.ttf')
            if font_pkg_path:
                font_pkg = ImageFont.truetype(font_pkg_path, size=max(16, int(qr_size * 0.14)))
            else:
                font_pkg = ImageFont.load_default()


            # Función para dibujar texto con contorno
            def draw_text_outline(draw_obj, pos, text, font, fill=(255, 255, 255),
                                outline_fill=(0, 0, 0), outline_w=3):
                """
                Dibuja un texto con contorno para mejorar visibilidad sobre cualquier fondo.
                """
                x, y = pos
                for dx in range(-outline_w, outline_w + 1):
                    for dy in range(-outline_w, outline_w + 1):
                        if dx != 0 or dy != 0:
                            draw_obj.text((x + dx, y + dy), text, font=font, fill=outline_fill)
                draw_obj.text(pos, text, font=font, fill=fill)


            # -------------------------
            # Añadir texto en la parte superior de la imagen
            # -------------------------
            print("! Paquete recibido:", paquete) #DEBUG

            if paquete:
                # Texto 1
                texto_arriba = f"Según tu paquete {paquete.upper()},"
                text_w = draw.textlength(texto_arriba, font=font_pkg)
                text_x = (img.width - text_w) / 2
                text_y = 10  # margen superior fijo (10 píxeles desde el borde superior)
                draw_text_outline(draw, (text_x, text_y), texto_arriba, font_pkg,
                                    fill=(255, 255, 255), outline_fill=(0, 0, 0), outline_w=2)

                # Texto 2, debajo del texto 1
                texto_arriba2 = "aquí tienes las indicaciones específicas"
                text_w2 = draw.textlength(texto_arriba2, font=font_pkg)
                text_x2 = (img.width - text_w2) / 2
                text_y2 = text_y + int(qr_size * 0.22)  # separación vertical del primer texto
                draw_text_outline(draw, (text_x2, text_y2), texto_arriba2, font_pkg,
                                        fill=(255, 255, 255), outline_fill=(0, 0, 0), outline_w=2)

                # Texto debajo del QR (sin cambios)
                texto_abajo = f"ENTRADA {paquete.upper()}"
                text_w3 = draw.textlength(texto_abajo, font=font_pkg)
                text_x3 = (img.width - text_w3) / 2
                text_y3 = qr_y + qr_size + 80  # posición debajo del QR
                draw_text_outline(draw, (text_x3, text_y3), texto_abajo, font_pkg,
                                fill=(0, 0, 0), outline_fill=(255, 255, 255), outline_w=2)


                # Añadir la imagen procesada a la lista
        imagenes.append(img)



    # --- unir todas las partes ---
    if not imagenes:
        raise ValueError("No se generaron imágenes (lista vacía).")
    # === UNIR TODAS LAS PARTES EN UNA SOLA IMAGEN ===
    ancho = max(img.width for img in imagenes)
    alto_total = sum(img.height for img in imagenes)
    imagen_final = Image.new('RGB', (ancho, alto_total), (255, 255, 255))

    y_offset = 0
    for img in imagenes:
        imagen_final.paste(img, (0, y_offset))
        y_offset += img.height

    return imagen_final


def limpiar_tipo_entrada(valor):
    if not isinstance(valor, str):
        return "EMPRENDEDOR"  # valor por defecto si es vacío
    # Extrae la parte después del guion
    tipo = valor.split('-')[-1].strip().upper()
    # Validar que sea uno de los permitidos
    if tipo not in ["FULL ACCES", "EMPRESARIAL", "EMPRENDEDOR"]:
        tipo = "EMPRENDEDOR"  # default
    return tipo

from django.conf import settings

from decimal import Decimal

class ParticipanteCreateView(CreateView):
    model = Participante
    fields = ['nombres','apellidos','dni','celular','correo','vendedor','tipo_entrada','cantidad', 'validado_admin', 'validado_contabilidad']
    template_name = 'cliente/participante_form.html'
    success_url = reverse_lazy('participante_lista')


    def form_valid(self, form):
        participante = form.save(commit=False)

        # Obtener los valores extra del formulario
        tipo_tarifa = self.request.POST.get("tipo_tarifa")
        precio_final = self.request.POST.get("precio_final")

        # Convertir precio_final a número si viene del formulario
        if precio_final:
            try:
                participante.precio = Decimal(precio_final)
            except:
                participante.precio = Decimal("0.00")

        # Calcular total correctamente
        cantidad = participante.cantidad or 0
        precio = participante.precio or Decimal("0.00")
        participante.total_pagar = cantidad * precio

        participante.save()

        print(f"✅ Guardado: {participante.nombres} | Precio: {participante.precio} | Total: {participante.total_pagar}")

        return super().form_valid(form)


class ParticipanteUpdateView(UpdateView):
    model = Participante
    fields = ['nombres','apellidos','dni','celular','correo','tipo_entrada','cantidad', 'vendedor', 'validado_admin', 'validado_contabilidad']
    template_name = 'cliente/participante_form.html'
    success_url = reverse_lazy('participante_lista')



class ParticipanteDeleteView(DeleteView):
    model = Participante
    template_name = 'cliente/participante_confirm_delete.html'
    success_url = reverse_lazy('participante_lista')
 
class ParticipanteListView(ListView):
    model = Participante
    template_name = 'cliente/lista.html'
    ordering = ['id']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")  # Obtiene el valor del input de búsqueda
        if q:
            queryset = queryset.filter(
                Q(nombres__icontains=q) | Q(dni__icontains=q)
            )
        return queryset



from django.shortcuts import redirect
from django.contrib import messages
import pandas as pd
from .models import Participante

def limpiar_tipo_entrada(valor):
    if pd.isna(valor):
        return "EMPRENDEDOR"
    # Tomar solo la parte después del guion y convertir a mayúscula
    return valor.split('-')[-1].strip().upper()

def valor_seguro(x):
    if pd.isna(x) or x == 0:
        return ""
    return str(x).strip()


def importar_excel(request):
    if request.method == "POST" and request.FILES.get('excel_file'):
        archivo = request.FILES['excel_file']
        try:
            # Leer Excel
            df = pd.read_excel(archivo)
            print(df.columns)  # Verifica los nombres de columnas

            # Asegúrate de que los nombres coincidan
            df = df.rename(columns={
                'Nombre': 'Nombre',
                'DNI': 'DNI',
                'TELEFONO': 'TELEFONO',
                'Correo electrónico': 'Correo',
                'ASESOR QUE TE INVITO': 'Vendedor',
                'Tipo de entrada': 'Tipo_Entrada'
            })

            # Extraer solo la parte después del guion
            df['Tipo_Entrada'] = df['Tipo_Entrada'].astype(str).apply(lambda x: x.split('-')[-1].strip())

            # Iterar y crear participantes
            for _, row in df.iterrows():
                if pd.isna(row['DNI']) or pd.isna(row['Nombre']):
                    continue  # Ignora filas vacías críticas

                telefono = ''
                if not pd.isna(row['TELEFONO']):
                    telefono = str(int(float(row['TELEFONO']))).strip()  # elimina .0 o decimales


                Participante.objects.create(
                    nombres=row['Nombre'],
                    apellidos="",  # Puedes separar apellido si quieres
                    dni=str(row['DNI']),
                    celular=telefono,
                    correo=row['Correo'] if not pd.isna(row['Correo']) else '',
                    vendedor=row['Vendedor'] if not pd.isna(row['Vendedor']) else '',
                    tipo_entrada=row['Tipo_Entrada'],
                    cantidad=1
                )

            messages.success(request, "✅ Participantes importados correctamente.")
        except Exception as e:
            messages.error(request, f"❌ Error al importar Excel: {e}")

    return redirect('participante_lista')

def generar_qr(request, token):
    """
    Genera un PNG con un QR que apunta a la vista 'validar_entrada' usando el token del participante.
    """

    # 1) Recuperar el participante o devolver 404 si no existe
    participante = get_object_or_404(Participante, token=token)

    # ---------- Construcción de la URL que queremos codificar ----------
    # Opción A: Forzar host con tu IP local (útil para pruebas cuando tu servidor corre en otra máquina)
    # 🔹 Construir la URL automáticamente (sin IP fija)
    url = request.build_absolute_uri(reverse('validar_entrada', args=[participante.token]))
    # Opción B (recomendada si el host actual es el correcto):
    # url = request.build_absolute_uri(reverse('validar_entrada', args=[participante.token]))
    # esto genera automáticamente "http(s)://<host>/ruta" usando request.scheme y request.get_host()

    print("👉 URL del QR generado:", url)  # solo para desarrollo; en producción usa logging

    # ---------- Crear el QR con qrcode.QRCode (más control que qrcode.make) ----------
    qr_obj = qrcode.QRCode(
        version=None,  # None -> la librería calcula el tamaño necesario automáticamente
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # tolerancia a errores (M es una buena elección)
        box_size=10,   # tamaño de cada "cuadro" del QR en pixeles
        border=4       # borde blanco (mínimo 4 recomendado por especificación)
    )
    qr_obj.add_data(url)
    qr_obj.make(fit=True)

    img = qr_obj.make_image(fill_color="black", back_color="white").convert("RGB")

    # ---------- Devolver la imagen como respuesta PNG ----------
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    # Si quieres que el navegador muestre el QR en línea:
    response['Content-Disposition'] = 'inline; filename="qr.png"'
    # Si deseas que lo descargue:
    # response['Content-Disposition'] = 'attachment; filename="qr.png"'

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

def validar_entrada(request, token):
    participante = get_object_or_404(Participante, token=token)

    if not participante.entrada_usada:
        participante.entrada_usada = True
        participante.fecha_ingreso = timezone.now()  # registra la hora de ingreso
        participante.save()
        mensaje = "Entrada válida, bienvenido al evento."
        estado = True
    else:
        mensaje = "Esta entrada ya ha sido usada."
        estado = False

    # Renderiza la página de validación
    return render(
        request,
        "cliente/entrada_valida.html" if estado else "cliente/entrada_usada.html",
        {"participante": participante, "mensaje": mensaje}
    )

def marcar_ingreso(request, pk):
    participante = get_object_or_404(Participante, pk=pk)
    if not participante.entrada_usada:  # solo marcar si aún no entró
        participante.entrada_usada = True
        participante.save()
    return redirect('lista')  # Ajusta al nombre de tu lista

def exportar_excel(request):
    # Obtener datos de los participantes
    participantes = Participante.objects.all().values()
    if not participantes:
        return HttpResponse("No hay participantes para exportar.", content_type="text/plain")

    df = pd.DataFrame(participantes)

    if 'paquete' in df.columns:
       df = df.drop(columns=['paquete'])

    # Crear buffer en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Participantes')

        workbook = writer.book
        worksheet = writer.sheets['Participantes']

        # 🎨 Estilos personalizados (morado y negro)
        header_font = Font(bold=True, color="FFFFFF")  # blanco
        header_fill = PatternFill(start_color="6A0DAD", end_color="6A0DAD", fill_type="solid")  # morado oscuro
        cell_font = Font(color="000000")  # texto negro
        center_alignment = Alignment(horizontal="center", vertical="center")
        border_style = Border(
            left=Side(border_style="thin", color="000000"),
            right=Side(border_style="thin", color="000000"),
            top=Side(border_style="thin", color="000000"),
            bottom=Side(border_style="thin", color="000000")
        )

        # ✅ Aplicar estilo a los encabezados
        for col_num, col_name in enumerate(df.columns, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_alignment
            cell.border = border_style

        # ✅ Aplicar estilo a las filas de datos
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, max_col=worksheet.max_column):
            for cell in row:
                cell.font = cell_font
                cell.border = border_style
                cell.alignment = Alignment(vertical="center")

        # ✅ Ajustar ancho automático de columnas
        for column_cells in worksheet.columns:
            max_length = 0
            column = get_column_letter(column_cells[0].column)
            for cell in column_cells:
                try:
                    cell_length = len(str(cell.value))
                    if cell_length > max_length:
                        max_length = cell_length
                except:
                    pass
            worksheet.column_dimensions[column].width = max_length + 2

        # ✅ Agregar una franja decorativa con el título
        worksheet.insert_rows(1)
        worksheet.merge_cells('A1:{}1'.format(get_column_letter(worksheet.max_column)))
        titulo = worksheet.cell(row=1, column=1)
        titulo.value = "🎟️ Lista de Participantes - Exportación"
        titulo.font = Font(bold=True, size=14, color="FFFFFF")
        titulo.fill = PatternFill(start_color="4B0082", end_color="4B0082", fill_type="solid")  # morado intenso
        titulo.alignment = Alignment(horizontal="center", vertical="center")

        # ✅ Agregar fecha de exportación
        fila_fecha = worksheet.max_row + 2
        worksheet.merge_cells(f"A{fila_fecha}:C{fila_fecha}")
        fecha_cell = worksheet.cell(row=fila_fecha, column=1)
        fecha_cell.value = f"📅 Exportado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        fecha_cell.font = Font(italic=True, color="555555")
        fecha_cell.alignment = Alignment(horizontal="left")

    # Preparar la respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=Participantes_MoradoNegro.xlsx'
    response.write(output.getvalue())
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


from django.shortcuts import render
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
from django.contrib.staticfiles import finders

def preview_imagen_final(request):
    """
    Vista que genera una imagen final compuesta por varias imágenes de fondo,
    personalizando una de ellas (parte02.jpg) con el nombre del cliente y un texto
    adicional. El resultado se devuelve como imagen en base64 para previsualizarla
    en el navegador sin necesidad de guardarla físicamente en disco.
    """

    # 1. Obtener el nombre del cliente desde la URL (ej: ?nombre=Leonardo)
    # Si no se pasa en la URL, se usa "Nombre Cliente" como valor por defecto.
    nombre_cliente = request.GET.get('nombre', 'Nombre Cliente')

    # 2. Buscar las imágenes parte01.jpg, parte02.jpg, ..., parte07.jpg en static/img
    partes = []
    for i in range(1, 8):
        ruta = finders.find (f'img/parte0{i}.jpg')  # localiza archivo estático
        if ruta:
            partes.append(ruta)

    # 3. Validación: si no hay imágenes encontradas, retornar error 404
    if not partes:
        return HttpResponse("No se encontraron imágenes para preview.", status=404)

    # Lista donde se guardarán las imágenes abiertas
    imagenes = []

    # 4. Procesar cada imagen encontrada
    for p in partes:
        img = Image.open(p)  # abrir la imagen con Pillow (PIL)

        # Si es la parte02.jpg, se le dibuja el texto personalizado
        if 'parte02.jpg' in p:
            draw = ImageDraw.Draw(img)

            try:
                # Cargar fuentes (asegúrate de que existan en static/fonts)
                font_path_bold = finders.find('fonts/arialbd.ttf')
                font_path_regular = finders.find('fonts/arial.ttf')

                # Calcular tamaño de letra dinámico según ancho de la imagen
                ancho_img = img.width
                font_title = ImageFont.truetype(font_path_bold, size=int(ancho_img/15))
                font_body = ImageFont.truetype(font_path_regular, size=int(ancho_img/25))
            except:
                # Si no encuentra las fuentes, usar fuentes por defecto
                font_title = ImageFont.load_default()
                font_body = ImageFont.load_default()

            # Función auxiliar para texto con borde (para mejor visibilidad)
            def draw_text_outline(draw_obj, position, text, font, fill,
                                  outline_fill='black', outline_width=2):
                x, y = position
                for dx in range(-outline_width, outline_width+1):
                    for dy in range(-outline_width, outline_width+1):
                        if dx != 0 or dy != 0:
                            draw_obj.text((x+dx, y+dy), text, font=font, fill=outline_fill)
                draw_obj.text(position, text, font=font, fill=fill)

            # Función auxiliar para centrar texto horizontalmente
            def draw_centered(draw_obj, y, text, font, fill=(255, 255, 255)):
                ancho_texto = draw_obj.textlength(text, font=font)
                x = (img.width - ancho_texto) / 2
                draw_text_outline(draw_obj, (x, y), text, font, fill)

            # Escribir el título del evento en la parte superior
            draw_centered(draw, 70, "TU ENTRADA A EL DESPERTAR DEL EMPRENDEDOR", font_title)

            # Escribir cuerpo del mensaje (varias líneas)
            y_text = 100
            lineas = [
                    f"¡Felicitaciones {nombre_cliente}!",
                    "",
                    "Estás dando un gran paso en tu vida profesional al adquirir tu entrada para",
                    "\"El despertar del emprendedor\".",
                    "",
                    "Mantente pendiente de nuestras redes y de los grupos de WhatsApp donde",
                    "compartiremos datos relevantes de este gran evento.",
                    "",
                    "Grupo de WhatsApp: https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT?mode=ems_wa_t",
                    "",
                    "¡Te damos la bienvenida a la familia!"
                ]

            for linea in lineas:
                draw_centered(draw, y_text, linea, font_body)
                y_text += int(ancho_img / 25) + 10  # espacio entre líneas proporcional

        # Agregar imagen (modificada o no) a la lista final
        imagenes.append(img)

    # 5. Crear una imagen nueva que una todas las partes en vertical
    ancho = max(img.width for img in imagenes)              # ancho máximo
    alto_total = sum(img.height for img in imagenes)        # altura sumada
    imagen_final = Image.new('RGB', (ancho, alto_total), (255, 255, 255))

    # Pegar cada imagen en su posición dentro del lienzo final
    y_offset = 0
    for img in imagenes:
        imagen_final.paste(img, (0, y_offset))
        y_offset += img.height

    # 6. Convertir la imagen resultante a base64 para incrustarla en HTML
    buffer = BytesIO()
    imagen_final.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')

    # 7. Retornar la imagen como <img src="data:..."> en la plantilla
    return render(request, 'cliente/preview_imagen.html', {'img_base64': img_base64})














