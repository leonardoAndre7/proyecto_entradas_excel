"""
Respaldo/restauración en base de datos de los archivos subidos.

Render usa un disco efímero: en cada despliegue o reinicio se borran los archivos de MEDIA_ROOT
(fondo del boleto, logos, comprobantes de pago). Cada archivo subido se copia a la tabla
ArchivoMedia y se vuelve a escribir en disco cuando falta (al arrancar, tras migrar y cuando se
necesita). Solo afecta a la app `cliente`; no toca `lotes` ni su plano.
"""
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# modelo -> campos de archivo que se respaldan (los QR se regeneran, no hace falta)
CAMPOS_RESPALDADOS = {
    "Evento": ("imagen_fondo", "logo", "banner"),
    "Voucher": ("imagen",),
}
TAMANO_MAXIMO = 8 * 1024 * 1024  # 8 MB por archivo


def respaldar_archivo(ruta_relativa):
    """Guarda en la base de datos el archivo (si existe en disco y aún no está respaldado)."""
    from .models import ArchivoMedia

    if not ruta_relativa:
        return False
    origen = os.path.join(settings.MEDIA_ROOT, ruta_relativa)
    if not os.path.isfile(origen):
        return False
    if ArchivoMedia.objects.filter(ruta=ruta_relativa).exists():
        return True
    if os.path.getsize(origen) > TAMANO_MAXIMO:
        logger.warning(f"Archivo demasiado grande para respaldar en la base de datos: {ruta_relativa}")
        return False
    with open(origen, "rb") as f:
        ArchivoMedia.objects.update_or_create(ruta=ruta_relativa, defaults={"contenido": f.read()})
    return True


def respaldar_instancia(instancia):
    """Respalda los campos de archivo de un Evento o Voucher recién guardado."""
    campos = CAMPOS_RESPALDADOS.get(instancia.__class__.__name__, ())
    for nombre in campos:
        archivo = getattr(instancia, nombre, None)
        if archivo and getattr(archivo, "name", None):
            try:
                respaldar_archivo(archivo.name)
            except Exception as e:  # el respaldo nunca debe impedir guardar
                logger.error(f"No se pudo respaldar {archivo.name}: {e}")


def restaurar_archivo(ruta_relativa):
    """Vuelve a escribir en disco un archivo respaldado si falta. True si existe al terminar."""
    from .models import ArchivoMedia

    if not ruta_relativa:
        return False
    destino = os.path.join(settings.MEDIA_ROOT, ruta_relativa)
    if os.path.exists(destino):
        return True
    try:
        fila = ArchivoMedia.objects.filter(ruta=ruta_relativa).first()
    except Exception:
        return False
    if not fila:
        return False
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(bytes(fila.contenido))
    logger.info(f"Archivo restaurado desde la base de datos: {ruta_relativa}")
    return True


def restaurar_todo():
    """Restaura todos los archivos respaldados que falten en disco. Devuelve cuántos."""
    from .models import ArchivoMedia

    restaurados = 0
    try:
        for ruta in ArchivoMedia.objects.values_list("ruta", flat=True):
            if not os.path.exists(os.path.join(settings.MEDIA_ROOT, ruta)):
                if restaurar_archivo(ruta):
                    restaurados += 1
    except Exception as e:  # tabla aún inexistente (antes de migrar), etc.
        logger.warning(f"No se pudieron restaurar los archivos: {e}")
    return restaurados


def respaldar_todo():
    """Respalda los archivos que ya existen en disco (útil tras instalar esta función)."""
    from .models import Evento, Voucher

    for modelo in (Evento, Voucher):
        try:
            for obj in modelo.objects.all():
                respaldar_instancia(obj)
        except Exception as e:
            logger.warning(f"No se pudo respaldar {modelo.__name__}: {e}")


# Plantillas de boleto que viajan en el repositorio (media/event_backgrounds/). Si el fondo que
# el evento tenía subido desaparece y no hay copia en la base de datos, se usa la del repo.
# clave: texto que debe aparecer en el nombre del evento (en minúsculas) -> ruta relativa en MEDIA_ROOT
PLANTILLAS_INCLUIDAS = {
    "despertar": "event_backgrounds/entrada_ede_2026.png",
}


def plantilla_incluida(evento):
    """Ruta relativa de la plantilla del repo que corresponde al evento, si existe en disco."""
    nombre = (evento.nombre or "").lower()
    for clave, ruta in PLANTILLAS_INCLUIDAS.items():
        if clave in nombre and os.path.exists(os.path.join(settings.MEDIA_ROOT, ruta)):
            return ruta
    return None


def enlazar_plantillas_faltantes():
    """
    Para cada evento cuyo fondo apunta a un archivo inexistente y sin copia en la base de datos,
    lo enlaza a la plantilla incluida en el repositorio. Devuelve cuántos eventos corrigió.
    """
    from .models import Evento

    corregidos = 0
    try:
        for ev in Evento.objects.exclude(imagen_fondo=""):
            if not ev.imagen_fondo:
                continue
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, ev.imagen_fondo.name)):
                continue
            if restaurar_archivo(ev.imagen_fondo.name):
                continue
            ruta = plantilla_incluida(ev)
            if ruta:
                ev.imagen_fondo.name = ruta
                ev.save(update_fields=["imagen_fondo"])
                corregidos += 1
    except Exception as e:
        logger.warning(f"No se pudieron enlazar las plantillas incluidas: {e}")
    return corregidos
