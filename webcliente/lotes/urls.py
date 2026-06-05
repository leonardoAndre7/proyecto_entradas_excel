from django.urls import path
from . import views

urlpatterns = [
    # Vista admin (requiere login + staff)
    path('plano/', views.ver_plano, name="plano"),

    # Vista pública para clientes (sin login, solo lectura)
    path('mapa/', views.ver_mapa_publico, name="mapa_publico"),

    # APIs (solo staff)
    path('guardar-lote/',    views.guardar_lote,        name="guardar_lote"),
    path('eliminar-lote/',   views.eliminar_lote,        name="eliminar_lote"),
    path('cambiar-estado/',  views.cambiar_estado_lote,  name="cambiar_estado_lote"),

    # Crear asesores (solo staff) — usuarios que solo pueden separar
    path('crear-asesor/',    views.crear_asesor,         name="crear_asesor"),

    # Actualización en vivo / precio
    path('estados/',         views.estados_lotes,        name="estados_lotes"),
    path('set-precio/',         views.set_precio_lote,    name="set_precio_lote"),
    path('set-precio-masivo/',  views.set_precio_masivo,  name="set_precio_masivo"),
    path('set-numero/',         views.set_numero_lote,    name="set_numero_lote"),
    path('tipo-cambio/',        views.tipo_cambio,        name="tipo_cambio"),

    # Reportes y respaldo (solo staff)
    path('reporte/',          views.reporte_asesores,        name="reporte_asesores"),
    path('reporte/excel/',    views.reporte_asesores_excel,  name="reporte_asesores_excel"),
    path('exportar-estados/', views.exportar_estados_excel,  name="exportar_estados_excel"),
]
