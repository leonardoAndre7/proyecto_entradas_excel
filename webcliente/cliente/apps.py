import sys
import threading

from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save


def _tras_migrar(sender, **kwargs):
    """Tras migrar (despliegue): respalda lo que haya en disco y restaura lo que falte."""
    from . import media_respaldo
    media_respaldo.respaldar_todo()
    media_respaldo.restaurar_todo()


def _al_guardar(sender, instance, **kwargs):
    from . import media_respaldo
    media_respaldo.respaldar_instancia(instance)


def _restaurar_en_segundo_plano():
    from django.db import connection
    from . import media_respaldo
    try:
        media_respaldo.restaurar_todo()
    finally:
        connection.close()


class ClienteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cliente'

    def ready(self):
        from .models import Evento, Voucher

        post_save.connect(_al_guardar, sender=Evento, dispatch_uid="respaldo_evento")
        post_save.connect(_al_guardar, sender=Voucher, dispatch_uid="respaldo_voucher")
        post_migrate.connect(_tras_migrar, sender=self, dispatch_uid="respaldo_tras_migrar")

        # Al arrancar el servidor (gunicorn/runserver) restaurar los archivos que Render haya borrado
        arranque = sys.argv[0] if sys.argv else ""
        if "gunicorn" in arranque or "runserver" in sys.argv:
            threading.Timer(5, _restaurar_en_segundo_plano).start()
