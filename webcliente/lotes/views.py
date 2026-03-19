from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Plano, Lote
import json
from django.contrib.auth.decorators import login_required


def ver_plano(request):

    plano = Plano.objects.first()

    # 🔥 Si no hay plano, evitar error
    if not plano:
        return render(request, "lotes/plano.html", {
            "plano": None,
            "lotes": json.dumps([]),
            "es_admin": request.user.is_staff
        })

    # 🔥 SOLO LOTES DE ESTE PLANO
    lotes = list(
        Lote.objects.filter(plano=plano).values(
            "id", "x", "y", "width", "height", "estado"
        )
    )

    return render(request, "lotes/plano.html", {
        "plano": plano,
        "lotes": json.dumps(lotes),
        "es_admin": request.user.is_staff  # 🔥 SOLO ADMIN REAL
    })


@login_required
def guardar_lote(request):

    if request.method == "POST":

        # 🔒 SOLO ADMIN
        if not request.user.is_staff:
            return JsonResponse({"error": "No autorizado"}, status=403)

        data = json.loads(request.body)

        plano = get_object_or_404(Plano, id=data["plano_id"])

        lote = Lote.objects.create(
            plano=plano,
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
            estado=data["estado"]  # 🔥 IMPORTANTE
        )

        return JsonResponse({
            "status": "ok",
            "id": lote.id
        })

    return JsonResponse({"error": "Método no permitido"}, status=405)


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