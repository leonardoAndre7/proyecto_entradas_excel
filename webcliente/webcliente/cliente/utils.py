import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from django.core.files import File
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.conf import settings
import pandas as pd
import qrcode
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