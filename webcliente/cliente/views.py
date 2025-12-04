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
from django.views.decorators.http import require_POST



@require_POST
def check_admin_masivo(request):
    # Actualiza todos los participantes marcando validado_admin = True
    Participante.objects.update(validado_admin=True)
    messages.success(request, "Se ha marcado Administración como validado para todos los participantes.")
    return redirect("participante_lista")  # Cambia por el nombre de tu url de lista



@require_POST
def check_contabilidad_masivo(request):
    # Actualiza todos los participantes marcando validado_contabilidad = True
    Participante.objects.update(validado_contabilidad=True)
    messages.success(request, "Se ha marcado Contabilidad como validado para todos los participantes.")
    return redirect("participante_lista")  # Cambia por el nombre de tu url de lista




def enviar_masivo(request):
    participantes = Participante.objects.filter()

    if not participantes.exists():
        messages.warning(request, "⚠️ No hay participantes registrados.")
        return redirect("participante_lista")

    enviados = 0
    errores = 0

    for participante in participantes:
        try:
            # ✅ Solo enviar si está validado por Admin y Contabilidad
            if not (participante.validado_admin and participante.validado_contabilidad):
                print(f"⏭️ Saltando {participante.nombres}: faltan validaciones.")
                continue

            print(f"📤 Enviando a {participante.nombres} ({participante.celular})")

            # ✅ Generar QR con dominio público
            url = f"{settings.BASE_URL}/validar/{participante.token}/"
            qr_img = qrcode.make(url).convert("RGB")

            # ✅ Crear imagen personalizada
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
            imagen_final.save(buffer, format="PNG")
            buffer.seek(0)

            # ✅ Subir imagen a ImgBB
            image_url = None
            try:
                api_key = settings.IMGBB_API_KEY
                encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
                response = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": api_key, "image": encoded_image},
                    timeout=20
                )
                if response.status_code == 200:
                    image_url = response.json()["data"]["url"]
                    print(f"🖼️ Imagen subida: {image_url}")
            except Exception as e:
                print(f"⚠️ Error subiendo imagen a ImgBB para {participante.nombres}: {e}")

            # ✅ Enviar correo
            try:
                asunto = "🎟️ Tu entrada - El Despertar del Emprendedor"
                html_mensaje = f"""
                <html><body>
                    <p>Hola {participante.nombres},</p>
                    <p>Tienes {participante.cantidad} Entradas para el evento.</p>
                    <p>Gracias por tu compra. Adjunto tu entrada personalizada.</p>
                    
                     <p>📱 Únete al grupo oficial del evento:</p>
                    <p>https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT</p>
                    
                    <img src="cid:entrada" style="max-width:100%; height:auto;">
                </body></html>
                """

                email = EmailMultiAlternatives(
                    subject=asunto,
                    body="Tu correo no soporta HTML.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[participante.correo],
                )
                email.attach_alternative(html_mensaje, "text/html")

                img = MIMEImage(buffer.getvalue())
                img.add_header('Content-ID', '<entrada>')
                img.add_header('Content-Disposition', 'inline', filename='entrada.png')
                email.attach(img)
                email.send()
                print(f"📧 Correo enviado a {participante.correo}")
            except Exception as e:
                print(f"⚠️ Error enviando correo a {participante.nombres}: {e}")

            # ✅ Enviar WhatsApp solo si ya habló con Twilio
            try:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                numero_twilio = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"

                # Normalizar número destino
                numero_limpio = "".join(filter(str.isdigit, participante.celular))
                if not numero_limpio.startswith("51"):
                    numero_limpio = "51" + numero_limpio
                numero_destino = f"whatsapp:+{numero_limpio}"

                mensaje = (
                    f"🎟️ *Confirmación de tu entrada - El Despertar del Emprendedor*\n\n"
                    f"¡Hola {participante.nombres}! 👋\n\n"
                    f"Tu pago fue confirmado ✅\n"
                    f"Tienes {participante.cantidad} entrada(s) para el evento.\n\n"
                    f"📱 Únete al grupo oficial del evento:\n"
                    f"https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT\n\n"
                    f"Nos vemos pronto 🙌"
                )

                if image_url:
                    message = client.messages.create(
                        from_=numero_twilio,
                        to=numero_destino,
                        body=mensaje,
                        media_url=[image_url]
                    )
                else:
                    message = client.messages.create(
                        from_=numero_twilio,
                        to=numero_destino,
                        body=mensaje
                    )

                print(f"✅ WhatsApp enviado a {participante.nombres}: {message.sid}")

            except Exception as e:
                print(f"⚠️ No se pudo enviar WhatsApp a {participante.nombres}: {e}")
                print("💡 Posible causa: el usuario no ha iniciado conversación con el número Twilio.")

            # ✅ Registrar envío
            RegistroCorreo.objects.update_or_create(
                participante=participante,
                defaults={"enviado": True, "fecha_envio": timezone.now()}
            )

            # ✅ Marcar como pago confirmado
            participante.pago_confirmado = True
            participante.save()

            enviados += 1

        except Exception as e:
            errores += 1
            print(f"❌ Error con {participante.nombres}: {e}")

    print(f"✅ Enviados: {enviados} | ❌ Errores: {errores}")
    messages.success(request, f"✅ Se enviaron {enviados} entradas correctamente. ({errores} errores)")
    return redirect("participante_lista")







from django.shortcuts import render, get_list_or_404, redirect
from django.utils import timezone
from django.contrib import messages

def marcar_ingreso(request, pk):
    participante = get_object_or_404(Previaparticipantes, pk=pk)
    
    if participante.entrada_usada:
        messages.warning(request, f"{participante.nombres} ya ingreso anteriormente.")
        return redirect("registro_participante")
    
    participante.entrada_usada = True
    participante.hora_ingreso = timezone.now()
    participante.save()
    
    messages.success(request, f"Ingreso registrado correctamente para {participante.nombres}.")
    return redirect("registro_participante")








##############################################################################################
# REGISTRO DE LOS CLIENTE 2     -------      EVENTO 2
##############################################################################################
def registro_participante(request):
    # Generar el nuevo código automáticamente
    ultimo = Previaparticipantes.objects.order_by('-id').first()
    numero = int(ultimo.cod_part.replace('CLI', '')) + 1 if ultimo else 1
    nuevo_cod = f"CLI{numero:03d}"

    # Siempre obtenemos todos los participantes
    participantes = Previaparticipantes.objects.order_by('cod_part')


    if request.method == 'POST':
        # 1️⃣ Carga masiva desde Excel
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            wb = openpyxl.load_workbook(excel_file)
            sheet = wb.active
            for row in sheet.iter_rows(min_row=2, values_only=True):
                nombres, dni, celular, correo = row[:4]
                ultimo = Previaparticipantes.objects.order_by('-id').first()
                numero = int(ultimo.cod_part.replace('CLI', '')) + 1 if ultimo else 1
                nuevo_cod_row = f"CLI{numero:03d}"
                Previaparticipantes.objects.create(
                    cod_part=nuevo_cod_row,
                    nombres=nombres,
                    dni=dni,
                    celular=celular,
                    correo=correo
                )
            messages.success(request, "Participantes cargados desde Excel correctamente.")
        else:
            participante = Previaparticipantes.objects.create(
                cod_part=nuevo_cod,
                nombres=request.POST.get('nombres'),
                dni=request.POST.get('dni'),
                celular=request.POST.get('celular'),
                correo=request.POST.get('correo')
            )
            messages.success(request, f"Participante {participante.nombres} registrado correctamente.")
        return redirect('registro_participante')

    return render(request, 'cliente/registro_participante.html', {
        'nuevo_cod': nuevo_cod,
        'participantes': participantes
    })
####################################################################################
###################################################################################



##############################################################################################
# ACTUALIZACION DE LOS CLIENTES 2     -------      EVENTO 2
##############################################################################################
def actualizar_participante_previa(request, pk):
    participante = get_object_or_404(Previaparticipantes, pk=pk)

    if request.method == 'POST':
        participante.nombres = request.POST.get('nombres')
        participante.dni = request.POST.get('dni')
        participante.celular = request.POST.get('celular')
        participante.correo = request.POST.get('correo')
        
        participante.save()

        return redirect('registro_participante')  # 🔹 Volvemos a la página principal

    return render(request, 'cliente/actualizar_participante_previo.html', {
        'participante': participante
    })
    
    
####################################################################################
###################################################################################



##############################################################################################
# ELIMINACION DE LOS CLIENTES 2     -------      EVENTO 2
##############################################################################################
def eliminar_participante_previa(request, pk):
    participante = get_object_or_404(Previaparticipantes, pk=pk)
    if request.method == "POST":
        participante.delete()
        return redirect('registro_participante') 
##########################################################################################
##########################################################################################




########################################################################################
##########################################################################################
#############         ENVIO DE WHATSAP Y CORREOS
############################################################################################
##############################################################################################
 
import os
import base64
import tempfile
from PIL import Image
from io import BytesIO
import qrcode
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from twilio.rest import Client
import requests
from decouple import config
import logging

# Configurar logger
logger = logging.getLogger(__name__)

def generar_qr_dinamico(participante, size=None):
    """
    Genera el QR dinámicamente con tamaño ajustable
    """
    try:
        # URL del QR (igual que en qr_preview)
        url = f"{settings.BASE_URL}{reverse('validar_entrada_previo', args=[str(participante.token)])}"
        
        # Crear QR (mismos parámetros que qr_preview)
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        
        # Crear imagen (mismos colores que qr_preview)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir a PIL Image
        qr_img = img.get_image()
        
        # Redimensionar si se especifica tamaño
        if size:
            qr_img = qr_img.resize(size, Image.Resampling.LANCZOS)
        
        return qr_img
        
    except Exception as e:
        logger.error(f"Error generando QR dinámico: {e}")
        raise

def get_background_image():
    """Obtiene la imagen de fondo asesor.jpeg"""
    fondo_path = os.path.join(settings.BASE_DIR, 'cliente', 'static', 'img', 'asesor.jpeg')
    
    if os.path.exists(fondo_path):
        return fondo_path
    
    # Buscar en otras ubicaciones posibles
    alternative_paths = [
        os.path.join(settings.BASE_DIR, 'static', 'img', 'asesor.jpeg'),
        os.path.join(settings.BASE_DIR, 'asesor.jpeg'),
    ]
    
    for path in alternative_paths:
        if os.path.exists(path):
            return path
    
    return None

def calcular_transformacion_cuadrilatero():
    """
    Calcula la transformación para el QR en un cuadrilátero irregular
    
    Coordenadas del cuadrilátero:
    - Izquierda arriba: (170, 405)
    - Izquierda abajo: (168, 974)
    - Derecha arriba: (735, 410)
    - Derecha abajo: (737, 979)
    
    Retorna: (pos_x, pos_y, ancho, alto) aproximados
    """
    # Como es casi un rectángulo, usamos aproximación
    # Calcular ancho promedio
    ancho_arriba = 735 - 170  # 565
    ancho_abajo = 737 - 168   # 569
    ancho = (ancho_arriba + ancho_abajo) // 2  # 567
    
    # Calcular alto promedio
    alto_izquierda = 974 - 405  # 569
    alto_derecha = 979 - 410    # 569
    alto = (alto_izquierda + alto_derecha) // 2  # 569
    
    # Posición: usar la esquina superior izquierda como referencia
    # Pero ajustar ligeramente porque no es perfectamente rectangular
    pos_x = min(170, 168)  # 168
    pos_y = min(405, 410)  # 405
    
    # Pequeños ajustes para centrar mejor
    pos_x += (abs(170 - 168)) // 2  # Ajuste por diferencia izquierda
    pos_y += (abs(405 - 410)) // 2  # Ajuste por diferencia superior
    
    return pos_x, pos_y, ancho, alto

def crear_entrada_con_qr(participante):
    """
    Crea la entrada combinada: asesor.jpeg + QR ajustado al cuadrilátero
    """
    try:
        # 1. Calcular dimensiones del cuadrilátero
        pos_x, pos_y, qr_width, qr_height = calcular_transformacion_cuadrilatero()
        
        logger.info(f"Cuadrilátero: pos=({pos_x}, {pos_y}), tamaño={qr_width}x{qr_height}")
        
        # 2. Generar el QR con el tamaño exacto del cuadrilátero
        qr_img = generar_qr_dinamico(participante, size=(qr_width, qr_height))
        logger.info(f"QR generado con tamaño: {qr_img.size}")
        
        # 3. Obtener la imagen de fondo
        fondo_path = get_background_image()
        
        if not fondo_path:
            # Si no hay fondo, devolver solo el QR
            logger.warning("No se encontró asesor.jpeg, usando solo QR")
            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer
        
        # 4. Cargar la imagen de fondo
        fondo = Image.open(fondo_path)
        
        # Convertir formatos si es necesario
        if fondo.mode == "RGBA":
            fondo = fondo.convert("RGB")
        
        # 5. Crear máscara de transformación si es necesario
        # Como las coordenadas forman casi un paralelogramo, 
        # podemos usar una transformación simple
        
        # Opción A: Si el cuadrilátero es casi rectangular (como en este caso)
        # Simplemente pegamos el QR en la posición calculada
        
        # 6. Crear copia del fondo
        entrada_completa = fondo.copy()
        
        # 7. Pegar el QR en la posición calculada
        # Nota: El QR ya tiene el tamaño correcto
        entrada_completa.paste(qr_img, (pos_x, pos_y))
        
        # ============================================================
        # 7.1 ✨ AGREGAR NOMBRE DEL PARTICIPANTE DEBAJO DEL QR (BLANCO)
        # ============================================================
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(entrada_completa)
        nombre = participante.nombres.upper()

        # Ruta a la fuente que sí existe
        font_path = os.path.join(settings.BASE_DIR, "cliente", "static", "fonts", "Roboto-Bold.ttf")

        # Ajuste automático del tamaño
        max_width = qr_width - 20
        font_size = 180  # tamaño grande inicial

        while font_size > 40:
            try:
                font = ImageFont.truetype(font_path, font_size)
            except:
                # fallback seguro
                font = ImageFont.truetype(font_path, 60)
                break

            bbox = draw.textbbox((0, 0), nombre, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                break

            font_size -= 10

        # centrar texto
        texto_x = pos_x + (qr_width // 2) - (text_width // 2)
        texto_y = pos_y + qr_height + 35

        # Dibujar texto en blanco con borde negro grueso
        draw.text(
            (texto_x, texto_y),
            nombre,
            font=font,
            fill="white",
            stroke_width=5,
            stroke_fill="black"
        )
# ============================================================
        # ============================================================

        
        # 8. Opcional: Dibujar el contorno del cuadrilátero para debug
        if settings.DEBUG:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(entrada_completa)
            
            # Dibujar el cuadrilátero
            puntos = [
                (170, 405),  # Izquierda arriba
                (168, 974),  # Izquierda abajo
                (737, 979),  # Derecha abajo
                (735, 410),  # Derecha arriba
            ]
            
            # Dibujar líneas
            for i in range(4):
                draw.line([puntos[i], puntos[(i+1)%4]], fill="red", width=2)
            
            # Marcar esquinas
            for punto in puntos:
                draw.ellipse([punto[0]-5, punto[1]-5, punto[0]+5, punto[1]+5], 
                           fill="green", outline="yellow")
        
        # 9. Guardar en buffer
        buffer = BytesIO()
        entrada_completa.save(buffer, format="JPEG", quality=95, optimize=True)
        buffer.seek(0)
        
        logger.info(f"Entrada creada exitosamente. Tamaño final: {entrada_completa.size}")
        
        return buffer
        
    except Exception as e:
        logger.error(f"Error creando entrada con QR: {e}", exc_info=True)
        raise
    
    
    
def crear_entrada_con_qr_transformado(participante):
    """
    Versión alternativa con transformación perspectiva para cuadrilátero irregular.
    Agrega nombre del participante debajo del QR con tamaño dinámico.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 1. Generar QR base
        qr_base = generar_qr_dinamico(participante, size=(600, 600))
        
        # 2. Obtener fondo
        fondo_path = get_background_image()
        if not fondo_path:
            buffer = BytesIO()
            qr_base.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer
        
        fondo = Image.open(fondo_path)
        if fondo.mode == "RGBA":
            fondo = fondo.convert("RGB")
        
        # 3. Coordenadas aproximadas del cuadrilátero
        ancho_promedio = ((735-170) + (737-168)) // 2
        alto_promedio = ((974-405) + (979-410)) // 2
        
        pos_x = 168
        pos_y = 405
        
        # 4. Redimensionar QR al tamaño aproximado
        qr_img = qr_base.resize((ancho_promedio, alto_promedio), Image.Resampling.LANCZOS)
        qr_width, qr_height = qr_img.size
        
        # 5. Crear copia del fondo y pegar QR
        entrada_completa = fondo.copy()
        entrada_completa.paste(qr_img, (pos_x, pos_y))
        
        # ============================================================
        # ✨ AGREGAR NOMBRE DEL PARTICIPANTE DEBAJO DEL QR
        # ============================================================
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(entrada_completa)
        nombre = participante.nombres.upper()

        # Ruta a la fuente que sí existe
        font_path = os.path.join(settings.BASE_DIR, "cliente", "static", "fonts", "Roboto-Bold.ttf")

        # Ajuste automático del tamaño
        max_width = qr_width - 20
        font_size = 180  # tamaño grande inicial

        while font_size > 40:
            try:
                font = ImageFont.truetype(font_path, font_size)
            except:
                # fallback seguro
                font = ImageFont.truetype(font_path, 60)
                break

            bbox = draw.textbbox((0, 0), nombre, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                break

            font_size -= 10

        # centrar texto
        texto_x = pos_x + (qr_width // 2) - (text_width // 2)
        texto_y = pos_y + qr_height + 35

        # Dibujar texto en blanco con borde negro grueso
        draw.text(
            (texto_x, texto_y),
            nombre,
            font=font,
            fill="white",
            stroke_width=5,
            stroke_fill="black"
        )
# ============================================================
        # ============================================================

        # 6. Guardar en buffer
        buffer = BytesIO()
        entrada_completa.save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        
        return buffer
    
    except Exception as e:
        logger.error(f"Error en transformación perspectiva: {e}", exc_info=True)
        # Fallback a la versión simple
        return crear_entrada_con_qr(participante)

    
    
    
    

def upload_buffer_to_imgbb(image_buffer, filename="entrada.jpg"):
    """Subir imagen desde buffer a ImgBB"""
    try:
        encoded_image = base64.b64encode(image_buffer.getvalue()).decode("utf-8")
        
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": settings.IMGBB_API_KEY,
                "image": encoded_image,
                "name": filename
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json().get("data", {}).get("url")
        else:
            logger.error(f"ImgBB API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error uploading to ImgBB: {e}")
        return None





def enviar_whatsapp_qr(request, cod_part):
    """
    Envía el QR dinámico sobre asesor.jpeg por WhatsApp y correo
    """
    participante = get_object_or_404(Previaparticipantes, cod_part=cod_part)
    
    # Crear la entrada combinada
    try:
        # Usar la versión con transformación precisa
        entrada_buffer = crear_entrada_con_qr_transformado(participante)
        
    except Exception as e:
        messages.error(request, f"❌ Error al crear la entrada: {e}")
        logger.error(f"Error creando entrada: {e}", exc_info=True)
        return redirect("registro_participante")
    
    # Guardar temporalmente para correo
    tmp_path = None
    try:
        tmp_path = os.path.join(tempfile.gettempdir(), f"entrada_{participante.id}.jpg")
        with open(tmp_path, 'wb') as f:
            f.write(entrada_buffer.getvalue())
        
        entrada_buffer.seek(0)
        
    except Exception as e:
        messages.error(request, f"❌ Error al guardar temporalmente: {e}")
        return redirect("registro_participante")
    
    # ======================================================
    # 1️⃣ ENVÍO POR WHATSAPP
    # ======================================================
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        numero_twilio = f"whatsapp:{settings.TWILIO_PHONE_NUMBER}"
        
        # Normalizar número celular
        celular = participante.celular or ""
        celular = "".join([c for c in celular if c.isdigit()])
        
        if not celular:
            messages.error(request, "❌ El participante no tiene número de celular.")
            return redirect("registro_participante")
        
        numero_destino = f"whatsapp:+51{celular}"
        
        # Subir entrada a ImgBB
        image_url = upload_buffer_to_imgbb(entrada_buffer, f"entrada_{participante.id}.jpg")
        
        mensaje_texto = (
            f"🎟️ *Aquí tienes tu entrada para El Renacer del Asesor*\n\n"
            f"Hola {participante.nombres}:\n\n"
            f"¡Gracias por ser parte de El Renacer del Asesor!\n"
            f"Adjunto encontrarás tu entrada oficial para el evento. Por favor, descárgala y guárdala, ya que será necesaria para tu acceso el día del evento.\n\n"
            f"*Detalles importantes:*\n\n"
            f"• *Evento:* El Renacer del Asesor\n"
            f"• *Fecha:* 14/12/2025\n"
            f"• *Lugar:* Pendiente\n\n"
            f"Te recomendamos llegar con anticipación para realizar el check-in sin inconvenientes.\n\n"
            f"¡Nos vemos pronto para vivir una experiencia que marcará un antes y un después en tu camino como asesor! 🚀"
        )
        
        if image_url:
            message = client.messages.create(
                from_=numero_twilio,
                to=numero_destino,
                body=mensaje_texto,
                media_url=[image_url]
            )


            
            messages.success(request, f"✅ Entrada enviada por WhatsApp a {participante.nombres}")
        else:
            client.messages.create(
                from_=numero_twilio,
                to=numero_destino,
                body=mensaje_texto + "\n\n⚠️ No se pudo adjuntar la entrada. Contacta al organizador."
            )
            
            messages.warning(request, f"⚠️ WhatsApp enviado sin imagen a {participante.nombres}")
             
    except Exception as e:
        logger.error(f"Error enviando WhatsApp: {e}")
        messages.error(request, f"❌ Error enviando WhatsApp: {str(e)[:100]}")
    
    # ======================================================
    # 2️⃣ ENVÍO POR CORREO
    # ======================================================
    # ======================================================
# 2️⃣ ENVÍO POR CORREO — HTML + FONDO DESDE TU DOMINIO
# ======================================================
    try:
        if participante.correo:
            from_email = config('EMAIL_HOST_USER1')
            password = config('EMAIL_HOST_PASSWORD1')

            asunto = "🎟️ Aquí tienes tu entrada para El Renacer del Asesor"

            import smtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = asunto
            msg["From"] = from_email
            msg["To"] = participante.correo

            # ---------------------------------------------
            # HTML CON FONDO: usa la imagen desde tu dominio
            # ---------------------------------------------
            html = f"""
            <html>
            <body style="margin:0; padding:0;">

                <!-- Fondo general -->
                <table width="100%" cellpadding="0" cellspacing="0" border="0"
                    style="
                        background-size: cover;
                        background-position: center;
                        padding: 40px 0;
                    ">
                <tr>
                    <td>

                    <!-- Caja de contenido -->
                    <table width="600" align="center" cellpadding="0" cellspacing="0"
                            style="
                            background: rgba(255, 255, 255, 0.92);
                            border-radius: 12px;
                            padding: 30px;
                            font-family: Arial, sans-serif;
                            box-shadow: 0 4px 25px rgba(0,0,0,0.2);
                            ">

                        <tr>
                        <td align="center">
                            <h1 style="margin:0; color:#222; font-size:28px;">
                            🎟️ El Renacer del Asesor
                            </h1>
                        </td>
                        </tr>

                        <tr>
                        <td style="padding-top:20px; font-size:18px; color:#333;">
                            Hola <strong>{participante.nombres}</strong>,
                        </td>
                        </tr>

                        <tr>
                        <td style="padding-top:15px; font-size:16px; color:#444;">
                            ¡Gracias por ser parte de <strong>El Renacer del Asesor</strong>!
                            Tu entrada oficial está adjunta a este correo.
                        </td>
                        </tr>

                        <tr>
                        <td style="padding-top:20px;">
                            <table width="100%" style="background:#fafafa; border-left:5px solid #007bff; padding:20px;">
                            <tr>
                                <td style="font-size:18px; color:#222;">
                                📌 <strong>Detalles del evento:</strong>
                                </td>
                            </tr>
                            <tr>
                                <td style="font-size:16px; color:#555;">
                                <ul style="padding-left:20px; margin:0;">
                                    <li>Evento: El Renacer del Asesor</li>
                                    <li>Ingreso con entrada adjunta</li>
                                </ul>
                                </td>
                            </tr>
                            </table>
                        </td>
                        </tr>

                        <tr>
                        <td style="padding-top:25px; font-size:17px; color:#007bff; font-weight:bold;">
                            Te recomendamos llegar con anticipación para el check-in.
                        </td>
                        </tr>

                        <tr>
                        <td style="padding-top:25px; font-size:16px; color:#444;">
                            ¡Nos vemos pronto para vivir una experiencia transformadora!
                        </td>
                        </tr>

                        <tr>
                        <td style="padding-top:30px; font-size:16px; color:#444;">
                            Saludos,<br>
                            <strong>Equipo El Renacer del Asesor</strong>
                        </td>
                        </tr>

                    </table>

                    </td>
                </tr>
                </table>

            </body>
            </html>
            """

            # El correo será HTML (NO texto simple)
            msg.set_content("Tu cliente de correo no soporta HTML.")
            msg.add_alternative(html, subtype="html")

            # -------------------------------
            # Adjuntar la entrada en JPG
            # -------------------------------
            with open(tmp_path, "rb") as f:
                msg.add_attachment(
                    f.read(),
                    maintype="image",
                    subtype="jpeg",
                    filename=f"entrada_{participante.id}.jpg"
                )

            # -------------------------------
            # Enviar correo
            # -------------------------------
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(from_email, password)
                server.send_message(msg)

            messages.success(request, f"📧 Entrada enviada por correo a {participante.correo}")

        else:
            messages.warning(request, f"⚠️ {participante.nombres} no tiene correo registrado.")

    except Exception as e:
        logger.error(f"Error enviando correo: {e}")
        messages.error(request, f"❌ Error enviando correo: {str(e)[:100]}")

    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception as e:
            logger.error(f"Error limpiando archivos: {e}")
      
    participante.enviado = True
    participante.save()


    return redirect("registro_participante")






def visualizar_cuadrilatero():
    """
    Crea una imagen de prueba para ver el cuadrilátero
    """
    from PIL import Image, ImageDraw
    
    # Crear imagen blanca
    img = Image.new('RGB', (1000, 1500), color='white')
    draw = ImageDraw.Draw(img)
    
    # Coordenadas del cuadrilátero
    puntos = [
        (170, 405),  # Izquierda arriba
        (168, 974),  # Izquierda abajo
        (737, 979),  # Derecha abajo
        (735, 410),  # Derecha arriba
    ]
    
    # Dibujar líneas
    for i in range(4):
        draw.line([puntos[i], puntos[(i+1)%4]], fill="red", width=3)
    
    # Marcar puntos con colores
    colores = ['green', 'blue', 'orange', 'purple']
    nombres = ['Izq-Arriba', 'Izq-Abajo', 'Der-Abajo', 'Der-Arriba']
    
    for i, (punto, color, nombre) in enumerate(zip(puntos, colores, nombres)):
        # Punto
        draw.ellipse([punto[0]-8, punto[1]-8, punto[0]+8, punto[1]+8], 
                    fill=color, outline='black')
        # Texto
        draw.text((punto[0]+10, punto[1]-10), f"{nombre}\n{punto}", fill='black')
    
    # Guardar
    img.save('cuadrilatero_test.jpg', quality=95)
    print("Imagen de prueba guardada como 'cuadrilatero_test.jpg'")
    
    # Mostrar dimensiones
    print(f"\nDimensiones del cuadrilátero:")
    print(f"Ancho superior: {735-170}px")
    print(f"Ancho inferior: {737-168}px")
    print(f"Alto izquierdo: {974-405}px")
    print(f"Alto derecho: {979-410}px")
    
    return img
 
###############################################################################
###############################################################################



#####################################
####################################
######################################

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

        headers = ['Código', 'Nombre', 'DNI', 'Celular', 'Correo']
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
            ws.cell(row=row_num, column=5, value=p.correo)

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
    data = [['Código', 'Nombre', 'DNI', 'Celular', 'Correo']]
    for p in participantes:
        data.append([
            p.cod_part,
            p.nombres,
            p.dni,
            p.celular,
            p.correo
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

####################################################
#####################################################
# PREVIEW QR - EVENTO 2
#######################################################
######################################################

import qrcode
from django.http import HttpResponse
from io import BytesIO
from django.urls import reverse
from django.conf import settings

def qr_preview(request, token):
    participante = get_object_or_404(Previaparticipantes, token=token)

    # URL del QR
    url = f"{settings.BASE_URL}{reverse('validar_entrada_previo', args=[str(participante.token)])}"

    # Crear QR
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer, content_type="image/png")





#####################################
####################################
##################################
#### LA VALIDACION DEL STAF

from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def validar_entrada_previo(request, token):
    """
    Valida la entrada de un participante previo mediante su token.
    Marca la entrada como usada solo si aún no fue utilizada.
    """

    # 1️⃣ Recuperar el participante
    participante = get_object_or_404(Previaparticipantes, token=token)

    # 2️⃣ Verificar si ya usó la entrada
    if participante.entrada_usada:
        # Ya se escaneó antes → pantalla de entrada repetida
        return render(request, "cliente/entrada_repetida.html", {"participante": participante})

    # 3️⃣ Marcar como usada y registrar hora
    participante.entrada_usada = True
    participante.hora_ingreso = timezone.now()
    participante.save()

    # 4️⃣ Mostrar pantalla de validación exitosa
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




###############################################################################
#################################################################################
# ENVIAR A TODOS WHATSAP Y CORREOS
################################################################################
##################################################################################
import os
import base64
import tempfile
import time
import logging
from io import BytesIO
from email.message import EmailMessage

from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMessage as DjangoEmailMessage  # opcional si prefieres
from twilio.rest import Client
import requests
from decouple import config

from cliente.models import Previaparticipantes

# Asumo que estas funciones están definidas en el mismo archivo o importadas:
# - crear_entrada_con_qr_transformado(participante) -> BytesIO (buffer con imagen JPEG)
# - upload_buffer_to_imgbb(buffer, filename) -> URL (o None)
# Si las tienes en otro módulo, importa: from .mi_modulo import crear_entrada_con_qr_transformado, upload_buffer_to_imgbb

logger = logging.getLogger(__name__)


def enviar_todos_whatsapp(request):
    """
    Envío masivo: por cada Previaparticipantes crea la entrada (QR + asesor.jpeg),
    sube a ImgBB, envía por WhatsApp (Twilio) y envía por correo si tiene.
    NO aplica filtros: envía a todos con celular (excluye nulos/vacíos).
    """
    if request.method != "POST":
        return redirect('registro_participante')

    participantes = Previaparticipantes.objects.exclude(celular__isnull=True).exclude(celular="").order_by('id')
    total = participantes.count()
    enviados_whatsapp = 0
    enviados_email = 0
    errores = 0

    messages.info(request, f"⏳ Iniciando envío masivo a {total} participantes. No cerrar navegador ni consola.")

    # Inicializar Twilio
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        numero_twilio = f"whatsapp:{settings.TWILIO_PHONE_NUMBER}"
    except Exception as e:
        logger.error(f"Error inicializando Twilio: {e}", exc_info=True)
        messages.error(request, "❌ Error inicializando Twilio. Revisa configuración.")
        return redirect('registro_participante')

    for idx, p in enumerate(participantes, start=1):
        tmp_path = None
        try:
            logger.info(f"[{idx}/{total}] Procesando participante id={p.id} {p.nombres}")

            # 1) Crear la entrada combinada (transformada). Reutiliza tu función existente.
            try:
                entrada_buffer = crear_entrada_con_qr_transformado(p)  # debe devolver BytesIO
            except Exception as e:
                logger.error(f"Error creando entrada para {p.id} - {p.nombres}: {e}", exc_info=True)
                errores += 1
                # continuar con el siguiente participante
                continue

            # 2) Guardar temporalmente (para adjuntar al correo si hace falta)
            try:
                tmp_path = os.path.join(tempfile.gettempdir(), f"entrada_{p.id}.jpg")
                with open(tmp_path, "wb") as f:
                    f.write(entrada_buffer.getvalue())
                entrada_buffer.seek(0)
            except Exception as e:
                logger.error(f"Error guardando temporal para {p.id}: {e}", exc_info=True)
                # No abortamos; intentaremos subir desde buffer
                tmp_path = None

            # 3) Subir a ImgBB (reutilizando la función que ya tienes)
            try:
                image_url = upload_buffer_to_imgbb(entrada_buffer, filename=f"entrada_{p.id}.jpg")
                if not image_url:
                    logger.warning(f"No se obtuvo image_url para {p.id}; se enviará mensaje sin imagen.")
            except Exception as e:
                logger.error(f"Error subiendo a ImgBB para {p.id}: {e}", exc_info=True)
                image_url = None

            # 4) Preparar número destino (normalizar)
            celular_raw = (p.celular or "").strip()
            celular_digits = "".join([c for c in celular_raw if c.isdigit()])
            if not celular_digits:
                logger.warning(f"{p.nombres} (id={p.id}) no tiene número válido. Omitido WhatsApp.")
            else:
                # Si no tiene código país, asumimos Perú (51)
                if not celular_digits.startswith("51"):
                    celular_digits = "51" + celular_digits
                numero_destino = f"whatsapp:+{celular_digits}"

                # 5) Mensaje
                mensaje_texto = (
                    f"🎟️ Hola {p.nombres}, tu entrada para *El Renacer del Asesor* está lista.\n\n"
                    f"📅 Fecha: 14/12/2025\n"
                    f"📍 Lugar: Pendiente\n\n"
                    "Adjuntamos tu entrada oficial. Por favor, descárgala y guárdala para el ingreso.\n\n"
                    "¡Nos vemos pronto! 🚀"
                )

                # 6) Envío por Twilio (con o sin media)
                try:
                    if image_url:
                        client.messages.create(
                            from_=numero_twilio,
                            to=numero_destino,
                            body=mensaje_texto,
                            media_url=[image_url]
                        )
                    else:
                        client.messages.create(
                            from_=numero_twilio,
                            to=numero_destino,
                            body=mensaje_texto
                        )
                    enviados_whatsapp += 1
                    logger.info(f"WhatsApp enviado a {p.nombres} -> {numero_destino}")
                except Exception as e:
                    logger.error(f"Error enviando WhatsApp a {p.id} ({p.nombres}): {e}", exc_info=True)

            # 7) Enviar correo si tiene
            if getattr(p, "correo", None):
                try:
                    # ======================================================
                    # 2️⃣ ENVÍO POR CORREO — HTML + FONDO DESDE TU DOMINIO
                    # ======================================================
                    from_email = config('EMAIL_HOST_USER1')
                    password = config('EMAIL_HOST_PASSWORD1')

                    asunto = "🎟️ Aquí tienes tu entrada para El Renacer del Asesor"

                    import smtplib
                    from email.message import EmailMessage

                    msg = EmailMessage()
                    msg["Subject"] = asunto
                    msg["From"] = from_email
                    msg["To"] = p.correo

                    # ---------------------------------------------
                    # HTML CON FONDO (desde tu dominio)
                    # ---------------------------------------------
                    html = f"""
                    <html>
                    <body style="margin:0; padding:0;">

                        <table width="100%" cellpadding="0" cellspacing="0" border="0"
                            style="
                                background-size: cover;
                                background-position: center;
                                padding: 40px 0;
                            ">
                        <tr>
                            <td>

                            <table width="600" align="center" cellpadding="0" cellspacing="0"
                                    style="
                                    background: rgba(255, 255, 255, 0.92);
                                    border-radius: 12px;
                                    padding: 30px;
                                    font-family: Arial, sans-serif;
                                    box-shadow: 0 4px 25px rgba(0,0,0,0.2);
                                    ">

                                <tr>
                                <td align="center">
                                    <h1 style="margin:0; color:#222; font-size:28px;">
                                    🎟️ El Renacer del Asesor
                                    </h1>
                                </td>
                                </tr>

                                <tr>
                                <td style="padding-top:20px; font-size:18px; color:#333;">
                                    Hola <strong>{p.nombres}</strong>,
                                </td>
                                </tr>

                                <tr>
                                <td style="padding-top:15px; font-size:16px; color:#444;">
                                    ¡Gracias por ser parte de <strong>El Renacer del Asesor</strong>!  
                                    Tu entrada oficial está adjunta a este correo.
                                </td>
                                </tr>

                                <tr>
                                <td style="padding-top:20px;">
                                    <table width="100%" style="background:#fafafa; border-left:5px solid #007bff; padding:20px;">
                                    <tr>
                                        <td style="font-size:18px; color:#222;">
                                        📌 <strong>Detalles del evento:</strong>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="font-size:16px; color:#555;">
                                        <ul style="padding-left:20px; margin:0;">
                                            <li>Evento: El Renacer del Asesor</li>
                                            <li>Ingreso con entrada adjunta</li>
                                        </ul>
                                        </td>
                                    </tr>
                                    </table>
                                </td>
                                </tr>

                                <tr>
                                <td style="padding-top:25px; font-size:17px; color:#007bff; font-weight:bold;">
                                    Te recomendamos llegar con anticipación para el check-in.
                                </td>
                                </tr>

                                <tr>
                                <td style="padding-top:25px; font-size:16px; color:#444;">
                                    ¡Nos vemos pronto para vivir una experiencia transformadora!
                                </td>
                                </tr>

                                <tr>
                                <td style="padding-top:30px; font-size:16px; color:#444;">
                                    Saludos,<br>
                                    <strong>Equipo El Renacer del Asesor</strong>
                                </td>
                                </tr>

                            </table>

                            </td>
                        </tr>
                        </table>

                    </body>
                    </html>
                    """

                    # Configurar cuerpo HTML
                    msg.set_content("Tu cliente de correo no soporta HTML.")
                    msg.add_alternative(html, subtype="html")

                    # Adjuntar entrada (JPG)
                    if tmp_path and os.path.exists(tmp_path):
                        with open(tmp_path, "rb") as f:
                            msg.add_attachment(
                                f.read(),
                                maintype="image",
                                subtype="jpeg",
                                filename=f"entrada_{p.id}.jpg"
                            )
                    else:
                        entrada_buffer.seek(0)
                        msg.add_attachment(
                            entrada_buffer.getvalue(),
                            maintype="image",
                            subtype="jpeg",
                            filename=f"entrada_{p.id}.jpg"
                        )

                    # Enviar correo
                    with smtplib.SMTP("smtp.gmail.com", 587) as server:
                        server.starttls()
                        server.login(from_email, password)
                        server.send_message(msg)

                    enviados_email += 1
                    messages.success(request, f"📧 Entrada enviada por correo a {p.correo}")

                except Exception as e:
                    logger.error(f"Error enviando correo HTML a {p.id} ({p.nombres}): {e}", exc_info=True)
                    messages.error(request, f"❌ Error enviando correo: {str(e)[:100]}")

            else:
                messages.warning(request, f"⚠️ {p.nombres} no tiene correo registrado.")

        finally:
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception as e:
                    logger.error(f"Error limpiando tmp_path {tmp_path}: {e}", exc_info=True)

            # Marcar como enviado
        p.enviado = True
        p.save()
        
           # ---------------------------
    # 🔥 RETURN FINAL OBLIGATORIO
    # ---------------------------
    summary = f"✅ Finalizado. WhatsApp enviados: {enviados_whatsapp}. Correos: {enviados_email}. Errores: {errores}."
    messages.success(request, summary)
    logger.info(summary)

    return redirect("registro_participante")

#########################################################
#########################################################



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
    participante.pago_confirmado = True
    participante.save()

    # ✅ Generar QR con dominio público
    url = f"{settings.BASE_URL}{reverse('validar_entrada', args=[participante.token])}"
    qr_img = qrcode.make(url).convert("RGB")

    # ✅ Crear imagen personalizada
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
    ruta_media = os.path.join(settings.MEDIA_ROOT, f"entrada_{participante.id}.png")
    imagen_final.save(ruta_media, format="PNG")

    # ✅ Enviar correo
    try:
        asunto = "🎟️ Confirmación de tu entrada - El Despertar del Emprendedor"
        html_mensaje = f"""
        <html><body>
            <p>Hola {participante.nombres},</p>
            <p>Tienes {participante.cantidad} Entradas para el evento.</p>
            <p>Adjunto encontrarás tu entrada personalizada para 
            <b>El Despertar del Emprendedor</b>.</p>
            <p>📱 Únete al grupo oficial del evento:</p>
             <p>https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT</p>
            <p>¡Nos vemos pronto!</p>
            <br>
            <img src="cid:entrada" style="max-width:100%; height:auto;">
        </body></html>
        """

        email = EmailMultiAlternatives(
            subject=asunto,
            body="Tu correo no soporta HTML.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[participante.correo],
        )
        email.attach_alternative(html_mensaje, "text/html")

        img = MIMEImage(buffer.getvalue())
        img.add_header('Content-ID', '<entrada>')
        img.add_header('Content-Disposition', 'inline', filename='entrada.png')
        email.attach(img)
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
    except Exception as e:
        print("❌ Error subiendo imagen:", e)

    # ✅ Enviar WhatsApp solo si el usuario ya habló con el número Twilio
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        numero_twilio = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"
        
        # Limpiar número del participante
        numero_limpio = "".join(filter(str.isdigit, participante.celular))
        if not numero_limpio.startswith("51"):
            numero_limpio = "51" + numero_limpio
        numero_destino = f"whatsapp:+{numero_limpio}"

        mensaje_whatsapp = (
            f"¡Hola {participante.nombres}! 👋\n\n"
            f"Tu pago fue confirmado ✅\n"
            f"Tienes {participante.cantidad} entradas para el evento 🎟️.\n\n"
            f"📱 Únete al grupo del evento:\n"
            f"https://chat.whatsapp.com/IJ394YIlCDcGOQLLupjyRT\n\n"
            f"Nos vemos pronto 🙌"
        )

        # Si hay imagen subida, enviamos con media_url
        if image_url:
            message = client.messages.create(
                from_=numero_twilio,
                to=numero_destino,
                body=mensaje_whatsapp,
                media_url=[image_url]
            )
        else:
            message = client.messages.create(
                from_=numero_twilio,
                to=numero_destino,
                body=mensaje_whatsapp
            )

        print("✅ WhatsApp enviado correctamente:", message.sid)

    except Exception as e:
        print("❌ No se pudo enviar WhatsApp (probablemente el usuario no escribió primero):", e)

    # ✅ Registrar envío
    registro, created = RegistroCorreo.objects.get_or_create(
        participante=participante,
        defaults={"enviado": True, "fecha_envio": timezone.now()}
    )
    if not created:
        registro.enviado = True
        registro.fecha_envio = timezone.now()
        registro.save()

    messages.success(request, "✅ Pago confirmado, correo y WhatsApp enviados.")
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
    if tipo not in ["FULL ACCESS", "EMPRESARIAL", "EMPRENDEDOR"]:
        tipo = "EMPRENDEDOR"  # default
    return tipo

from django.conf import settings

from decimal import Decimal



class ParticipanteCreateView(CreateView):
    model = Participante
    fields = [
        'nombres', 'apellidos', 'dni', 'celular', 'correo',
        'vendedor', 'tipo_entrada', 'cantidad',
        'validado_admin', 'validado_contabilidad'
    ]
    template_name = 'cliente/participante_form.html'
    success_url = reverse_lazy('participante_lista')

    def form_valid(self, form):
        participante = form.save(commit=False)

        # Obtener datos adicionales del formulario
        tipo_tarifa = self.request.POST.get("tipo_tarifa")
        precio_final = self.request.POST.get("precio_final")

        # Guardar el precio
        if precio_final:
            try:
                participante.precio = Decimal(precio_final)
            except:
                participante.precio = Decimal("0.00")

        # Calcular total
        cantidad = participante.cantidad or 0
        participante.total_pagar = cantidad * participante.precio
        participante.save()

        # Guardar múltiples vouchers (si existen)
        vouchers = self.request.FILES.getlist('vouchers')
        for archivo in vouchers:
            Voucher.objects.create(participante=participante, imagen=archivo)

        print(f"✅ Guardado: {participante.nombres} | {len(vouchers)} vouchers")

        return super().form_valid(form)



class ParticipanteUpdateView(UpdateView):
    model = Participante
    fields = [
        'nombres', 'apellidos', 'dni', 'celular', 'correo',
        'tipo_entrada', 'cantidad', 'vendedor',
        'validado_admin', 'validado_contabilidad'
    ]
    template_name = 'cliente/participante_form.html'
    success_url = reverse_lazy('participante_lista')

    def form_valid(self, form):
        participante = form.save(commit=False)

        # Actualizar precio y total si cambia
        precio_final = self.request.POST.get("precio_final")
        if precio_final:
            try:
                participante.precio = Decimal(precio_final)
            except:
                participante.precio = Decimal("0.00")

        cantidad = participante.cantidad or 0
        participante.total_pagar = cantidad * participante.precio
        participante.save()

        # Si agregan nuevos vouchers al editar
        vouchers = self.request.FILES.getlist('vouchers')
        for archivo in vouchers:
            Voucher.objects.create(participante=participante, imagen=archivo)

        print(f"✏️ Actualizado: {participante.nombres} | +{len(vouchers)} vouchers")

        return super().form_valid(form)


class ParticipanteDeleteView(DeleteView):
    model = Participante
    template_name = 'cliente/participante_confirm_delete.html'
    success_url = reverse_lazy('participante_lista')
 
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

@method_decorator(login_required(login_url='/login/'), name='dispatch')
class ParticipanteListView(ListView):
    model = Participante
    template_name = 'cliente/lista.html'
    ordering = ['id']

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")
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
            df = pd.read_excel(archivo)
            print("Columnas en Excel:", df.columns.tolist())
            
            # Normalizar los nombres de columnas
            df.columns = df.columns.str.strip()
            df = df.rename(columns={
                'Nombre': 'Nombre',
                'DNI': 'DNI', 
                'TELEFONO': 'TELEFONO',
                'Correo electrónico': 'Correo',
                'ASESOR QUE TE INVITO': 'Vendedor',
                'Tipo de entrada': 'Tipo_Entrada'
            })

            # Diccionario de tarifas (CORREGIDO - más robusto)
            tarifas = {
                "FULL ACCESS": {"PREVENTA1": 1050, "PREVENTA2": 1500, "PREVENTA3": 2100, "PUERTA": 3000},
                "EMPRESARIAL": {"PREVENTA1": 525, "PREVENTA2": 750, "PREVENTA3": 1050, "PUERTA": 1800},
                "EMPRENDEDOR": {"PREVENTA1": 105, "PREVENTA2": 150, "PREVENTA3": 300, "PUERTA": 750},
            }

            enviados = 0
            errores = 0
            
            for _, row in df.iterrows():
                try:
                    if pd.isna(row['DNI']) or pd.isna(row['Nombre']):
                        continue
                    
                    telefono = ''
                    if not pd.isna(row['TELEFONO']):
                        telefono = str(row['TELEFONO']).replace('.0', '').strip()
                    
                    # 👇 NUEVA LÓGICA MEJORADA para interpretar tipo de entrada
                    tipo_texto = str(row['Tipo_Entrada']).strip().upper()
                    
                    # Limpiar y normalizar el texto
                    tipo_texto = tipo_texto.replace("ACCES", "ACCESS")
                    
                    # Buscar el tipo de entrada en el texto
                    tipo_encontrado = None
                    tarifa_encontrada = None
                    
                    # Primero buscar el TIPO (FULL ACCESS, EMPRESARIAL, EMPRENDEDOR)
                    for tipo_entrada in tarifas.keys():
                        if tipo_entrada in tipo_texto:
                            tipo_encontrado = tipo_entrada
                            break
                    
                    # Si no encontró tipo, usar por defecto
                    if not tipo_encontrado:
                        tipo_encontrado = "EMPRENDEDOR"  # O el que prefieras por defecto
                    
                    # Luego buscar la TARIFA (PREVENTA1, PREVENTA2, etc.)
                    for tarifa in tarifas[tipo_encontrado].keys():
                        if tarifa in tipo_texto:
                            tarifa_encontrada = tarifa
                            break
                    
                    # Si no encontró tarifa, usar PREVENTA1 por defecto
                    if not tarifa_encontrada:
                        tarifa_encontrada = "PREVENTA1"
                    
                    # Obtener el precio
                    precio = tarifas[tipo_encontrado].get(tarifa_encontrada, 0)
                    
                    # Debug: imprimir lo que encontró
                    print(f"Texto: {tipo_texto} → Tipo: {tipo_encontrado}, Tarifa: {tarifa_encontrada}, Precio: {precio}")
                    
                    Participante.objects.create(
                        nombres=row['Nombre'],
                        apellidos="",
                        dni=str(row['DNI']),
                        celular=telefono,
                        correo=row['Correo'] if not pd.isna(row['Correo']) else '',
                        vendedor=row['Vendedor'] if not pd.isna(row['Vendedor']) else '',
                        tipo_entrada=tipo_encontrado,
                        cantidad=1,
                        precio=precio
                    )
                    enviados += 1
                    
                except Exception as e:
                    print(f"❌ Error importando fila {row.get('Nombre', '(sin nombre)')}: {e}")
                    errores += 1
            
            messages.success(request, f"✅ Participantes importados: {enviados}. Errores: {errores}")
            
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

"""
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
"""  

from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def validar_entrada(request, token):
    """
    Solo el staff puede validar la entrada.
    """
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

from .forms import VoucherForm 

def subir_voucher(request, participante_id):
    participante = get_object_or_404(Participante, id=participante_id)
    
    if request.method == "POST" and request.FILES.get('voucher_file'):
        archivo = request.FILES['voucher_file']
        # Crear voucher
        Voucher.objects.create(participante=participante, imagen=archivo)
        messages.success(request, "Voucher subido correctamente.")
    else:
        messages.error(request, "No se seleccionó ningún archivo.")
    
    return redirect('registro_participante')  # Cambia por la URL de tu registro










