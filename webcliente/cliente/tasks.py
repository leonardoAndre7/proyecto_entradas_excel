import os
import tempfile
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.files import File

from twilio.rest import Client

from cliente.models import Previaparticipantes, EmailEnviado
from cliente.utils import (
    crear_entrada_con_qr_transformado,
    upload_buffer_to_imgbb,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
    retry_backoff=True
)
def enviar_todos_whatsapp_task(self):
    participantes = Previaparticipantes.objects.exclude(
        celular__isnull=True
    ).exclude(celular="").order_by("id")

    enviados_whatsapp = 0
    enviados_email = 0
    errores = 0

    # ==========================
    # INICIALIZAR TWILIO
    # ==========================
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )
    numero_twilio = f"whatsapp:{settings.TWILIO_PHONE_NUMBER}"

    for p in participantes:
        tmp_path = None

        try:
            # ==========================
            # CREAR ENTRADA CON QR
            # ==========================
            entrada_buffer = crear_entrada_con_qr_transformado(p)

            tmp_path = os.path.join(
                tempfile.gettempdir(),
                f"entrada_{p.id}.jpg"
            )

            with open(tmp_path, "wb") as f:
                f.write(entrada_buffer.getvalue())

            entrada_buffer.seek(0)

        except Exception as e:
            errores += 1
            logger.error(
                f"❌ Error creando entrada participante {p.id}: {e}",
                exc_info=True
            )
            continue  # sin entrada no tiene sentido seguir

        # ==========================
        # WHATSAPP (INDEPENDIENTE)
        # ==========================
        try:
            celular = "".join(c for c in (p.celular or "") if c.isdigit())

            if celular:
                if not celular.startswith("51"):
                    celular = "51" + celular

                image_url = upload_buffer_to_imgbb(
                    entrada_buffer,
                    f"entrada_{p.id}.jpg"
                )

                mensaje_whatsapp = (
                    f"🎟️ *El Renacer del Asesor*\n\n"
                    f"Hola {p.nombres},\n\n"
                    "Tu entrada oficial ya está lista.\n"
                    "Adjuntamos la imagen para tu ingreso.\n\n"
                    "¡Te esperamos! 🚀"
                )

                client.messages.create(
                    from_=numero_twilio,
                    to=f"whatsapp:+{celular}",
                    body=mensaje_whatsapp,
                    media_url=[image_url] if image_url else None,
                )

                enviados_whatsapp += 1

        except Exception as e:
            logger.error(
                f"❌ Error WhatsApp participante {p.id}: {e}",
                exc_info=True
            )

        # ==========================
        # EMAIL (INDEPENDIENTE)
        # ==========================
        try:
            if p.correo:
                asunto = "🎟️ Aquí tienes tu entrada para El Renacer del Asesor"

                html = f"""
                <html>
                <body style="margin:0;padding:0;background:#f2f2f2;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td align="center" style="padding:40px 0;">

                                <table width="600" cellpadding="0" cellspacing="0"
                                    style="background:#ffffff;border-radius:12px;
                                    font-family:Arial,sans-serif;
                                    box-shadow:0 4px 25px rgba(0,0,0,.2);
                                    padding:30px;">

                                    <tr>
                                        <td align="center">
                                            <h1 style="margin:0;color:#222;">
                                                🎟️ El Renacer del Asesor
                                            </h1>
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="padding-top:20px;font-size:18px;color:#333;">
                                            Hola <strong>{p.nombres}</strong>,
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="padding-top:15px;font-size:16px;color:#444;">
                                            ¡Gracias por ser parte de <strong>El Renacer del Asesor</strong>!
                                            Tu entrada oficial está adjunta a este correo.
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="padding-top:20px;">
                                            <table width="100%"
                                                style="background:#fafafa;
                                                border-left:5px solid #007bff;
                                                padding:20px;">
                                                <tr>
                                                    <td style="font-size:16px;color:#555;">
                                                        📌 <strong>Detalles del evento</strong>
                                                        <ul>
                                                            <li>Evento: El Renacer del Asesor</li>
                                                            <li>Ingreso con entrada adjunta</li>
                                                        </ul>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="padding-top:25px;font-size:16px;color:#007bff;">
                                            Te recomendamos llegar con anticipación.
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="padding-top:25px;font-size:16px;color:#444;">
                                            ¡Nos vemos pronto!
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="padding-top:30px;font-size:16px;color:#444;">
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

                registro_email = EmailEnviado.objects.create(
                    participante=p,
                    destinatario=p.correo,
                    asunto=asunto,
                    cuerpo_html=html,
                )

                with open(tmp_path, "rb") as f:
                    registro_email.adjunto.save(
                        f"entrada_{p.id}.jpg",
                        File(f),
                        save=True
                    )

                email = EmailMessage(
                    subject=asunto,
                    body=html,
                    from_email="EDE Evento <noreply@ede-evento.com>",
                    to=[p.correo],
                )
                email.content_subtype = "html"

                with open(tmp_path, "rb") as f:
                    email.attach(
                        f"entrada_{p.id}.jpg",
                        f.read(),
                        "image/jpeg"
                    )

                email.send()

                registro_email.enviado = True
                registro_email.save()

                enviados_email += 1

        except Exception as e:
            errores += 1
            logger.error(
                f"❌ Error Email participante {p.id}: {e}",
                exc_info=True
            )

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        p.enviado = True
        p.save(update_fields=["enviado"])

    return {
        "whatsapp": enviados_whatsapp,
        "email": enviados_email,
        "errores": errores,
    }
