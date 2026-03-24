from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Plano, Lote
import json
from django.contrib.auth.decorators import login_required

def ver_plano(request):

    plano = Plano.objects.first()

    if not plano:
        return render(request, "lotes/plano.html", {
            "plano": None,
            "lotes": json.dumps([]),
            "es_admin": request.user.is_staff
        })

    lotes_qs = Lote.objects.filter(plano=plano)

    lotes = []

    for l in lotes_qs:
        lotes.append({
            "id": l.id,
            "x": l.x,
            "y": l.y,
            "width": l.width,
            "height": l.height,
            "estado": l.estado,
            # 🔥 ASEGURAR LISTA REAL
            "puntos": list(l.puntos) if l.puntos else None
        })

    return render(request, "lotes/plano.html", {
        "plano": plano,
        "lotes": json.dumps(lotes),
        "es_admin": request.user.is_staff
    })





@login_required
def guardar_lote(request):

    if request.method == "POST":

        if not request.user.is_staff:
            return JsonResponse({"error": "No autorizado"}, status=403)

        data = json.loads(request.body)

        plano = get_object_or_404(Plano, id=data["plano_id"])

        # 🔥 detectar si es polígono o rectángulo
        puntos = data.get("puntos", None)

        lote = Lote.objects.create(
            plano=plano,
            puntos=puntos,  # puede ser None o lista

            # 🔥 SOLO si es rectángulo
            x=data.get("x"),
            y=data.get("y"),
            width=data.get("width"),
            height=data.get("height"),

            estado=data["estado"]
        )

        return JsonResponse({
            "status": "ok",
            "id": lote.id
        })
    


@login_required
def eliminar_lote(request):

    if request.method == "POST":

        # 🔒 SOLO ADMIN
        if not request.user.is_staff:
            return JsonResponse({"error": "No autorizado"}, status=403)

        data = json.loads(request.body)

        lote = get_object_or_404(Lote, id=data["id"])
        lote.delete()

        return JsonResponse({"status": "ok"})

    return JsonResponse({"error": "Método no permitido"}, status=405)