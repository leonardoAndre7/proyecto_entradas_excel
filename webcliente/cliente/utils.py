import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from django.core.files import File
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.conf import settings
import pandas as pd
import qrcode
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files import File
from django.core.mail import EmailMessage
from django.conf import settings
import os
from PIL import Image
from django.contrib.staticfiles import finders

def enviar_correo_participante(participante):
    # ==============================
    # 📌 Primer correo: Entrada con QR
    # ==============================
    asunto1 = f"¡{participante.nombres}, tu entrada para EL DESPERTAR DEL EMPRENDEDOR! 🎉​🎉​🎉​"
    
    mensaje1_texto = f"""
    Hola {participante.nombres},

    Adjunto encontrarás tu entrada personalizada.

    👉​👉​👉​ No olvides guardarla y mostrarla el día del evento.

    Según tu paquete ({participante.tipo_entrada}), aquí tienes las indicaciones específicas.

    ¡Nos vemos muy pronto para vivir esta gran experiencia!

    Un abrazo,
    EQUIPO EL DESPERTAR DEL EMPRENDEDOR
    """

    mensaje1_html = f"""
    <p><b>TU ENTRADA A EL DESPERTAR DEL EMPRENDEDOR🎉​🎉​🎉</b></p>
    <br>

    
    
    <p>Hola <b>{participante.nombres}</b>,</p>
    <p>¡Gracias por unirte a <b>EL DESPERTAR DEL EMPRENDEDOR!</b></p>

    <p>Adjunto encontrarás tu entrada personalizada:</p>
    <p><b>👉​👉​👉 No olvides guardarla y mostrarla el día del evento.</b></p>
    <br>

    <p>Según tu paquete <b>{participante.tipo_entrada}</b>, aquí tienes las indicaciones específicas:</p>
    <ul>
        {"<li>Acceso VIP + Networking exclusivo</li>" if participante.tipo_entrada == "EMPRESARIAL" else ""}
        {"<li>Acceso general + Talleres emprendedores</li>" if participante.tipo_entrada == "EMPRENDEDOR" else ""}
        {"<li>Full access a todas las conferencias + material digital</li>" if participante.tipo_entrada == "FULL ACCES" else ""}
    </ul>
    <br>

    <p>¡Nos vemos muy pronto para vivir esta gran experiencia!</p>
    <br>
    <p>Un abrazo,<br>
    <b>EQUIPO EL DESPERTAR DEL EMPRENDEDOR</b></p>
    <br>
    <p>--------------------------------------------------------</p>
    <br>
    <p>Quedo a la espera de tu confirmación y propuesta de desarrollo</p>
    <br>
    <p>Saludos Cordiales</p>
    <p><b>Camila Simon</b></p>
    """


    email1 = EmailMultiAlternatives(
        asunto1,
        mensaje1_texto,
        settings.DEFAULT_FROM_EMAIL,
        [participante.correo],
    )
    email1.attach_alternative(mensaje1_html, "text/html")

    # Adjuntar QR si existe
    if participante.qr:
        email1.attach_file(participante.qr.path)

    # 👇 Aquí agregas el print para ver el HTML generado en consola
    print("==== HTML DEL CORREO ====")
    print(mensaje1_html)
    print("==========================")

    email1.send(fail_silently=False)

    # ==============================
    # 📌 Segundo correo: Confirmación
    # ==============================
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

def sincronizar_excel_local():
    from cliente.models import Participante  # ✅ import aquí para evitar import circular
    archivo_excel = "cliente/data/cliente.xlsx"
    
    # Leer Excel
    df = pd.read_excel(archivo_excel)
    
    # Recorrer filas y actualizar o crear registros
    for _, fila in df.iterrows():
        Participante.objects.update_or_create(
            dni=fila['DNI'],  # columna "DNI" en tu Excel
            defaults={
                'nombres': fila['Nombre'],           # corregido: 'nombres' según tu modelo
                'pago_confirmado': str(fila['Pagado']).strip().lower() == 'sí'  # columna "Pagado"
            }
        )



def generar_imagen_final(participante, partes_path_list, tipo_fuente="arial.ttf"):
    """
    Combina varias imágenes, coloca QR y texto según tipo de entrada.
    
    participante: objeto Participante
    partes_path_list: lista de rutas de imágenes a combinar
    tipo_fuente: fuente para el texto
    """
    # --- Cargar y combinar imágenes ---
    imagenes = [Image.open(p) for p in partes_path_list]
    
    # Calcular tamaño final: altura = suma de todas, ancho = máximo ancho
    ancho_final = max(img.width for img in imagenes)
    alto_final = sum(img.height for img in imagenes)
    
    imagen_final = Image.new('RGB', (ancho_final, alto_final), (255, 255, 255))
    
    # Pegar imágenes una sobre otra
    y_offset = 0
    for img in imagenes:
        imagen_final.paste(img, (0, y_offset))
        y_offset += img.height
    
    # --- Generar QR ---
    qr_content = f"{participante.cod_cliente}-{participante.dni}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    
    img_qr = qr.make_image(fill_color="darkblue", back_color="white").convert('RGB')
    qr_size = 150
    img_qr = img_qr.resize((qr_size, qr_size))
    
    # Pegar QR en esquina inferior derecha
    posicion_qr = (ancho_final - qr_size - 50, alto_final - qr_size - 50)
    imagen_final.paste(img_qr, posicion_qr)
    
    # --- Agregar texto tipo de entrada ---
    draw = ImageDraw.Draw(imagen_final)
    try:
        font = ImageFont.truetype(tipo_fuente, 60)
    except:
        font = ImageFont.load_default()
    
    texto = f"Entrada {participante.tipo_entrada.upper()}"
    ancho_texto, alto_texto = draw.textsize(texto, font=font)
    
    # Pegar texto en la parte superior central
    posicion_texto = ((ancho_final - ancho_texto) // 2, 50)
    draw.text(posicion_texto, texto, font=font, fill=(255, 0, 0))
    
    # --- Guardar en buffer ---
    buffer = BytesIO()
    imagen_final.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer


def preview_imagen_final():
    # Construir rutas de las imágenes
    base_path = os.path.join(settings.STATIC_ROOT, 'img')
    partes = [os.path.join(base_path, f"parte0{i}.jpg") for i in range(1, 8)]

    # Abrir imágenes
    imagenes = [Image.open(p) for p in partes]

    # Calcular tamaño final
    ancho = max(img.width for img in imagenes)
    alto_total = sum(img.height for img in imagenes)
    imagen_final = Image.new('RGB', (ancho, alto_total), (255, 255, 255))

    # Combinar imágenes verticalmente
    y_offset = 0
    for img in imagenes:
        imagen_final.paste(img, (0, y_offset))
        y_offset += img.height

    # Mostrar preview (abre la imagen en el visor de imágenes de tu sistema)
    imagen_final.show()


def generar_qr(participante, logo_path='ruta/logo.png'):
    qr_content = f"{participante.cod_cliente}-{participante.dni}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)

    img = qr.make_image(fill_color="darkblue", back_color="white").convert('RGB')

    # Agregar logo
    logo = Image.open(logo_path)
    logo_size = 50
    logo = logo.resize((logo_size, logo_size))
    pos = ((img.size[0]-logo_size)//2, (img.size[1]-logo_size)//2)
    img.paste(logo, pos)

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    participante.qr.save(f"{participante.cod_cliente}.png", File(buffer), save=False)
    participante.save(update_fields=['qr'])
    
    
    
    
       
    
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
        font_size = 80  # tamaño grande inicial

        while font_size > 25:
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










def generar_qr_en_memoria(participante, size):
    import qrcode
    from PIL import Image

    if participante:
        qr_content = f"{participante.cod_cliente}-{participante.dni}"
    else:
        qr_content = "QR-DE-PRUEBA"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color="darkblue",
        back_color="white"
    ).convert("RGB")  # 🔥 CAMBIO CLAVE

    img = img.resize(size, Image.LANCZOS)

    return img












###############################################################
###############################################################

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
        font_size = 120  # tamaño grande inicial

        while font_size > 50:
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
    
import base64
import requests
      

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
    

    