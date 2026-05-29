from celery import shared_task
from django.core.mail import EmailMessage

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 10})
def enviar_correo(self, asunto, cuerpo, destinatario):
    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        to=[destinatario]
    )
    email.content_subtype = "html"
    email.send()
