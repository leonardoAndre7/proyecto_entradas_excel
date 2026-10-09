"""
App de puerta: escaneo de QR sin login de usuario.

- El dispositivo canjea un código de puerta (CodigoPuerta) por un token firmado y lo guarda.
- Ese token solo sirve para validar entradas del evento del código. No da acceso a nada más.
- Las reglas de ingreso viven en Participante.registrar_ingreso() (única fuente de verdad).
"""
import json
from urllib.parse import quote, urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import CodigoPuerta, Evento, Participante, PerfilUsuario, ahora_actual

SALT = "puerta.v1"
MAX_FALLOS = 8          # intentos de código errados por IP...
VENTANA_FALLOS = 15 * 60  # ...dentro de este tiempo (segundos) antes de bloquear
MAX_FALLOS_GLOBAL = 60    # tope de fallos entre TODAS las IP por ventana (frena ataques distribuidos)
TOKEN_MAX_EDAD = 10 * 24 * 3600


def _ip(request):
    # El proxy de Render agrega la IP real AL FINAL de X-Forwarded-For; las anteriores las controla el cliente.
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (xff.split(",")[-1].strip() if xff else request.META.get("REMOTE_ADDR", "")) or "?"


def _json(data, status=200):
    resp = JsonResponse(data, status=status)
    resp["Cache-Control"] = "no-store"
    return resp


def _cuerpo(request):
    try:
        datos = json.loads(request.body.decode() or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _codigo_desde_request(request):
    """Devuelve (CodigoPuerta, None) o (None, motivo)."""
    token = request.headers.get("X-Puerta-Token", "")
    try:
        datos = signing.loads(token, salt=SALT, max_age=TOKEN_MAX_EDAD)
        codigo = CodigoPuerta.objects.select_related("evento").get(pk=datos["c"])
    except (signing.BadSignature, KeyError, CodigoPuerta.DoesNotExist):
        return None, "sesion_invalida"
    if not codigo.activo:
        return None, "revocado"
    if not codigo.vigente:
        return None, "vencido"
    return codigo, None


MOTIVOS_SESION = {
    "sesion_invalida": "Este dispositivo no está autorizado. Ingresa el código de puerta.",
    "revocado": "Este código fue revocado. Pide uno nuevo.",
    "vencido": "Este código ya venció. Pide uno nuevo.",
}


# ---------- Páginas de la app (públicas, sin datos) ----------
@never_cache
@require_GET
def puerta_app(request):
    resp = render(request, "cliente/puerta_app.html")
    return resp


@require_GET
def puerta_manifest(request):
    data = {
        "name": "EDE Puerta",
        "short_name": "EDE Puerta",
        "description": "Escaneo de entradas en la puerta del evento",
        "start_url": "/puerta/",
        "scope": "/puerta/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "lang": "es",
        "icons": [
            {"src": static("puerta/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("puerta/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("puerta/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    }
    resp = HttpResponse(json.dumps(data), content_type="application/manifest+json")
    resp["Cache-Control"] = "no-cache"
    return resp


@require_GET
def puerta_sw(request):
    """Service worker servido desde /puerta/ para que su alcance cubra la app."""
    js = render(request, "cliente/puerta_sw.js", {
        "lib": static("puerta/html5-qrcode.min.js"),
        "icono": static("puerta/icon-192.png"),
    }).content
    resp = HttpResponse(js, content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    resp["Service-Worker-Allowed"] = "/puerta/"
    return resp


# ---------- API ----------
@csrf_exempt
@require_POST
def puerta_acceso(request):
    """Canjea el código de puerta por un token firmado. Limita intentos por IP."""
    clave = f"puerta_fallos_{_ip(request)}"
    if cache.get(clave, 0) >= MAX_FALLOS or cache.get("puerta_fallos_global", 0) >= MAX_FALLOS_GLOBAL:
        return _json({"ok": False, "error": "Demasiados intentos. Espera unos minutos."}, 429)

    codigo_txt = str(_cuerpo(request).get("codigo", ""))[:40]
    codigo = CodigoPuerta.objects.select_related("evento").filter(
        codigo_hash=CodigoPuerta.hash_codigo(codigo_txt)).first() if codigo_txt.strip() else None

    if codigo is None:
        for k in (clave, "puerta_fallos_global"):
            try:
                cache.add(k, 0, VENTANA_FALLOS)
                cache.incr(k)
            except ValueError:
                cache.set(k, 1, VENTANA_FALLOS)
        return _json({"ok": False, "error": "Código incorrecto."}, 403)
    if not codigo.activo:
        return _json({"ok": False, "error": MOTIVOS_SESION["revocado"]}, 403)
    if not codigo.vigente:
        return _json({"ok": False, "error": MOTIVOS_SESION["vencido"]}, 403)

    cache.delete(clave)
    token = signing.dumps({"c": codigo.pk}, salt=SALT)
    return _json({"ok": True, "token": token, "dispositivo": codigo.nombre, "evento": codigo.evento.nombre})


@never_cache
@require_GET
def puerta_estado(request):
    """El dispositivo pregunta si su token sigue siendo válido (al abrir la app)."""
    codigo, motivo = _codigo_desde_request(request)
    if codigo is None:
        return _json({"ok": False, "motivo": motivo, "error": MOTIVOS_SESION[motivo]}, 401)
    return _json({"ok": True, "dispositivo": codigo.nombre, "evento": codigo.evento.nombre})


def _token_desde_qr(texto):
    texto = str(texto or "").strip()[:300]
    if "/" in texto:
        texto = [seg for seg in urlparse(texto).path.split("/") if seg][-1:] or [""]
        texto = texto[0]
    return texto.strip().lower()


def _nombre_publico(p):
    """Nombre + inicial del apellido. Nunca DNI ni correo."""
    ap = (p.apellidos or "").strip()
    return f"{(p.nombres or '').strip()} {ap[:1] + '.' if ap else ''}".strip() or "Participante"


@csrf_exempt
@require_POST
def puerta_validar(request):
    codigo, motivo = _codigo_desde_request(request)
    if codigo is None:
        return _json({"ok": False, "motivo": motivo, "error": MOTIVOS_SESION[motivo]}, 401)

    token = _token_desde_qr(_cuerpo(request).get("qr"))
    if not token:
        return _json({"ok": True, "valido": False, "motivo": "no_encontrado", "mensaje": "QR no reconocido."})

    with transaction.atomic():
        # select_for_update evita que dos puertas validen la misma entrada a la vez
        # of=("self",): bloquea solo la fila del participante (un LEFT JOIN con FOR UPDATE falla en Postgres)
        p = Participante.objects.select_for_update(of=("self",)).filter(token=token).first()
        if p is None:
            return _json({"ok": True, "valido": False, "motivo": "no_encontrado",
                          "mensaje": "QR no reconocido."})
        if p.evento_id != codigo.evento_id:
            return _json({"ok": True, "valido": False, "motivo": "otro_evento",
                          "mensaje": "Esta entrada es de otro evento."})
        valido, mensaje = p.registrar_ingreso()

    CodigoPuerta.objects.filter(pk=codigo.pk).update(ultimo_uso=ahora_actual(),
                                                     escaneos=F('escaneos') + 1)
    tarifa = p._tarifa_efectiva()
    return _json({
        "ok": True,
        "valido": valido,
        "motivo": "ok" if valido else (getattr(p, "ultimo_motivo", None) or "duplicado"),
        "mensaje": mensaje,
        "nombre": _nombre_publico(p),
        "tipo": (tarifa.tipo_entrada if tarifa else p.tipo_entrada) or "",
        "cantidad": p.cantidad,
    })


# ---------- Panel de códigos (solo SUPERADMIN) ----------
def _es_superadmin(user):
    return PerfilUsuario.objects.filter(user=user, rol="SUPERADMIN").exists()


@never_cache
@login_required(login_url="/participantes/login/")
def puerta_panel(request):
    if not _es_superadmin(request.user):
        return redirect("dashboard_eventos")

    nuevo = None
    error = None
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "crear":
            evento = get_object_or_404(Evento, pk=request.POST.get("evento"))
            nombre = (request.POST.get("nombre") or "").strip()[:80]
            vence = None
            if request.POST.get("vence"):
                vence = parse_datetime(request.POST["vence"])
                if vence and timezone.is_naive(vence):
                    vence = timezone.make_aware(vence, timezone.get_current_timezone())
            vence = vence or CodigoPuerta.vencimiento_por_defecto(evento)
            if not nombre:
                error = "Escribe un nombre para el dispositivo (ej. Puerta 1)."
            elif vence <= ahora_actual():
                error = "La fecha de vencimiento ya pasó."
            else:
                obj, claro = CodigoPuerta.generar(evento, nombre, vence)
                texto = (f"Hola {nombre}, este es tu código para escanear entradas en {evento.nombre}:\n\n"
                         f"*{claro}*\n\n"
                         "1) Instala la app EDE Puerta.\n2) Ábrela, escribe el código y acepta el permiso de cámara.\n"
                         f"El código vence el {timezone.localtime(vence):%d/%m/%Y %H:%M}. No lo compartas.")
                nuevo = {"obj": obj, "codigo": claro, "wa": "https://wa.me/?text=" + quote(texto)}
        elif accion in ("revocar", "reactivar"):
            CodigoPuerta.objects.filter(pk=request.POST.get("id")).update(activo=(accion == "reactivar"))
            return redirect("puerta_panel")

    codigos = list(CodigoPuerta.objects.select_related("evento"))
    ahora = ahora_actual()
    for c in codigos:
        c.estado = "revocado" if not c.activo else ("vencido" if c.vence_en <= ahora else "activo")
    return render(request, "cliente/puerta_panel.html", {
        "eventos": Evento.objects.all().order_by("-id"),
        "codigos": codigos,
        "n_activos": sum(c.estado == "activo" for c in codigos),
        "n_escaneos": sum(c.escaneos for c in codigos),
        "nuevo": nuevo,
        "error": error,
        "ahora": ahora,
    })
