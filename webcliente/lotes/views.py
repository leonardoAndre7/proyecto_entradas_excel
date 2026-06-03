from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Plano, Lote
import json


def _get_lotes_data(plano):
    """Devuelve la lista de lotes del plano como JSON-serializable."""
    lotes = []
    for l in Lote.objects.filter(plano=plano):
        lotes.append({
            "id":     l.id,
            "x":      l.x,
            "y":      l.y,
            "width":  l.width,
            "height": l.height,
            "estado": l.estado,
            "puntos": list(l.puntos) if l.puntos else None,
        })
    return lotes


# ──────────────────────────────────────────────────────────────
# VISTA ADMIN — solo staff, puede modificar estados
# URL: /plano/
# ──────────────────────────────────────────────────────────────
@login_required(login_url='/participantes/login/')
def ver_plano(request):
    if not request.user.is_staff:
        # Si es usuario normal, redirigir a la vista pública
        return redirect('mapa_publico')

    plano = Plano.objects.first()
    lotes = _get_lotes_data(plano) if plano else []

    return render(request, "lotes/plano_admin.html", {
        "plano": plano,
        "lotes": json.dumps(lotes),
    })


# ──────────────────────────────────────────────────────────────
# VISTA PÚBLICA — sin login, solo lectura
# URL: /mapa/
# ──────────────────────────────────────────────────────────────
def ver_mapa_publico(request):
    plano = Plano.objects.first()
    lotes = _get_lotes_data(plano) if plano else []

    # Estadísticas para el panel de resumen
    total      = len(lotes)
    vendidos   = sum(1 for l in lotes if l['estado'] == 'vendido')
    reservados = sum(1 for l in lotes if l['estado'] == 'reservado')
    disponibles = total - vendidos - reservados

    return render(request, "lotes/plano_publico.html", {
        "plano":       plano,
        "lotes":       json.dumps(lotes),
        "total":       total,
        "vendidos":    vendidos,
        "reservados":  reservados,
        "disponibles": disponibles,
    })


# ──────────────────────────────────────────────────────────────
# API — cambiar estado (solo staff)
# ──────────────────────────────────────────────────────────────
@login_required(login_url='/participantes/login/')
def cambiar_estado_lote(request):
    if request.method == "POST":
        if not request.user.is_staff:
            return JsonResponse({"error": "No autorizado"}, status=403)
        data       = json.loads(request.body)
        lote       = get_object_or_404(Lote, id=data["id"])
        nuevo_estado = data.get("estado")
        if nuevo_estado in ["disponible", "vendido", "reservado"]:
            lote.estado = nuevo_estado
            lote.save()
            return JsonResponse({"status": "ok", "estado": lote.estado})
        return JsonResponse({"error": "Estado inválido"}, status=400)
    return JsonResponse({"error": "Método no permitido"}, status=405)


# ──────────────────────────────────────────────────────────────
# API — guardar lote (solo staff)
# ──────────────────────────────────────────────────────────────
@login_required(login_url='/participantes/login/')
def guardar_lote(request):
    if request.method == "POST":
        if not request.user.is_staff:
            return JsonResponse({"error": "No autorizado"}, status=403)
        data  = json.loads(request.body)
        plano = get_object_or_404(Plano, id=data["plano_id"])
        lote  = Lote.objects.create(
            plano=plano,
            puntos=data.get("puntos"),
            x=data.get("x"), y=data.get("y"),
            width=data.get("width"), height=data.get("height"),
            estado=data["estado"]
        )
        return JsonResponse({"status": "ok", "id": lote.id})


# ──────────────────────────────────────────────────────────────
# API — eliminar lote (solo staff)
# ──────────────────────────────────────────────────────────────
@login_required(login_url='/participantes/login/')
def eliminar_lote(request):
    if request.method == "POST":
        if not request.user.is_staff:
            return JsonResponse({"error": "No autorizado"}, status=403)
        data = json.loads(request.body)
        lote = get_object_or_404(Lote, id=data["id"])
        lote.delete()
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Método no permitido"}, status=405)
