from django.urls import path
from . import views

urlpatterns = [

    path('plano/', views.ver_plano, name="plano"),
    path('guardar-lote/', views.guardar_lote, name="guardar_lote"),
    path("eliminar-lote/", views.eliminar_lote),


]