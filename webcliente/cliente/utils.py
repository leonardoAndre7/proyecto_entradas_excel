import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from django.core.files import File
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.conf import settings


def enviar_correo_participante(participante):
    # ==============================
    # 📌 Primer correo: Entrada con QR
    # ==============================
    asunto1 = f"¡{participante.nombres}, tu entrada para EL DESPERTAR DEL EMPRENDEDOR!"
    
    mensaje1_texto = f"""
    Hola {participante.nombres},

    Adjunto encontrarás tu entrada personalizada.

    = No olvides guardarla y mostrarla el día del evento.

    Según tu paquete ({participante.tipo_entrada}), aquí tienes las indicaciones específicas.

    ¡Nos vemos muy pronto para vivir esta gran experiencia!

    Un abrazo,
    EQUIPO EL DESPERTAR DEL EMPRENDEDOR
    """

    mensaje1_html = f"""
    <p>Hola <b>{participante.nombres}</b>,</p>

    <p>Adjunto encontrarás tu entrada personalizada:</p>
    <p><b>= No olvides guardarla y mostrarla el día del evento.</b></p>
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