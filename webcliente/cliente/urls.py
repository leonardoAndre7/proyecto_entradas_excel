from django.urls import path
from .views import ParticipanteListView, ParticipanteCreateView, ParticipanteUpdateView, ParticipanteDeleteView,panel_control, reenviar_correo, confirmar_pago
from . import views

urlpatterns = [
    path('', ParticipanteListView.as_view(), name='participante_lista'),
    path('participantes/', ParticipanteListView.as_view(), name='lista'),
    path('participantes/agregar/', ParticipanteCreateView.as_view(), name='participante_agregar'),
    path('participantes/editar/<int:pk>/editar', ParticipanteUpdateView.as_view(), name='participante_editar'),
    path('participantes/eliminar/<int:pk>/eliminar', ParticipanteDeleteView.as_view(), name='participante_eliminar'),
    path('exportar-excel/', views.exportar_excel, name='exportar_excel'),
    path('<int:pk>/qr/', views.mostrar_qr, name='mostrar_qr'),
    path('confirmar-pago/<int:pk>/', confirmar_pago, name='confirmar_pago'),
    path('panel-control/', panel_control, name='panel_control'),
    path('reenviar/<int:registro_id>/', reenviar_correo, name='reenviar_correo'),
    path("exportar-excel_control/", views.exportar_excel_control, name="exportar_excel_control"),
    path("exportar-pdf/", views.exportar_pdf_control, name="exportar_pdf"),
]
