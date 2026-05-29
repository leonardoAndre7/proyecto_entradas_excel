from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from cliente.models import Evento, Participante
from cliente.views import enviar_correo_con_smtp_evento

class Command(BaseCommand):
    help = "Envía recordatorios automáticos por correo a los participantes de eventos próximos en los siguientes 3 días."

    def handle(self, *args, **options):
        # Buscar eventos que se realizan en los próximos 3 días
        hoy = timezone.now().date()
        limite_fecha = hoy + timedelta(days=3)
        eventos = Evento.objects.filter(fecha_evento__gte=hoy, fecha_evento__lte=limite_fecha)

        if not eventos.exists():
            self.stdout.write("No hay eventos programados para los próximos 3 días.")
            return

        for evento in eventos:
            participantes = Participante.objects.filter(evento=evento, pago_confirmado=True)
            self.stdout.write(f"Enviando recordatorios para el evento '{evento.nombre}'...")
            
            exitos = 0
            for p in participantes:
                asunto = f"⏰ Recordatorio Oficial: Se acerca el evento {evento.nombre}"
                html_mensaje = f"""
                <html>
                <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f071c; color: #f8f9fa; padding: 2rem;">
                    <div style="max-width: 600px; margin: 0 auto; background: rgba(20, 10, 35, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 2.5rem; text-align: center;">
                        <h2 style="color: #00e676; font-size: 1.8rem; font-weight: 800;">¡Hola, {p.nombres}! 👋</h2>
                        <p style="font-size: 1.1rem; color: #e1bee7; margin-bottom: 1.5rem;">Falta muy poco para el gran día. Te recordamos los detalles de tu acceso para <strong>{evento.nombre}</strong>.</p>
                        
                        <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 1.2rem; text-align: left; margin-bottom: 1.5rem;">
                            <div style="margin-bottom: 0.5rem;"><span style="color: rgba(255, 255, 255, 0.5); font-weight: 600;">Fecha:</span> <strong style="color: #fff;">{evento.fecha_evento}</strong></div>
                            <div style="margin-bottom: 0.5rem;"><span style="color: rgba(255, 255, 255, 0.5); font-weight: 600;">Categoría:</span> <strong style="color: #fff;">{p.tipo_entrada|default:"GENERAL"}</strong></div>
                            <div><span style="color: rgba(255, 255, 255, 0.5); font-weight: 600;">Entradas Adquiridas:</span> <strong style="color: #fff;">{p.cantidad}</strong></div>
                        </div>

                        <p style="font-size: 0.95rem; color: #ffffff; line-height: 1.5;">Por favor, asegúrate de llevar tu entrada oficial impresa o en formato digital en tu celular. El código QR será escaneado en la entrada del recinto.</p>
                        <br>
                        <p style="font-weight: bold; color: #ba68c8;">¡Te esperamos con ansias! 🚀</p>
                    </div>
                </body>
                </html>
                """
                
                # Adjuntar entrada si existe en el modelo
                buffer = None
                if p.qr:
                    try:
                        import os
                        from io import BytesIO
                        from django.conf import settings
                        from cliente.views import generar_imagen_personalizada
                        import qrcode
                        
                        base_url = settings.BASE_URL.rstrip("/")
                        url_val = f"{base_url}/validar/{p.token}/"
                        qr_img = qrcode.make(url_val).convert("RGB")
                        imagen_final = generar_imagen_personalizada(p, qr_img)
                        
                        if imagen_final:
                            buffer = BytesIO()
                            imagen_final.save(buffer, format='PNG')
                            buffer.seek(0)
                    except Exception as e:
                        self.stdout.write(f"No se pudo cargar la imagen del boleto para {p.nombres}: {e}")
                
                if enviar_correo_con_smtp_evento(p, asunto, html_mensaje, buffer):
                    exitos += 1
            
            self.stdout.write(self.style.SUCCESS(f"✅ Se enviaron con éxito {exitos} recordatorios para el evento '{evento.nombre}'."))
