from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # 👈 Solo esta línea basta

urlpatterns = [
    path('', views.ParticipanteListView.as_view(), name='participante_lista'),
    path('participantes/', views.ParticipanteListView.as_view(), name='lista'),
    path('participantes/agregar/', views.ParticipanteCreateView.as_view(), name='participante_agregar'),
    path('participantes/editar/<int:pk>/editar', views.ParticipanteUpdateView.as_view(), name='participante_editar'),
    path('participantes/eliminar/<int:pk>/eliminar', views.ParticipanteDeleteView.as_view(), name='participante_eliminar'),

    path('exportar-excel/', views.exportar_excel, name='exportar_excel'),
    path("participantes/validar/<str:token>/", views.validar_entrada, name="validar_entrada"),
    path('qr/<str:token>/', views.generar_qr, name='generar_qr'),
    path('qr/mostrar/<int:pk>/', views.mostrar_qr, name='mostrar_qr'),

    path('confirmar-pago/<int:pk>/', views.confirmar_pago, name='confirmar_pago'),
    path('panel-control/', views.panel_control, name='panel_control'),
    path('participantes/reenviar/<int:pk>/', views.reenviar_correo, name='reenviar_correo'),
    path("exportar-excel_control/", views.exportar_excel_control, name="exportar_excel_control"),
    path("validar/<str:token>/", views.validar_entrada, name="validar_entrada"),
    path("exportar-pdf/", views.exportar_pdf_control, name="exportar_pdf"),
    path("registros/json/", views.registros_json, name="registros_json"),
    path('participantes/<int:pk>/marcar-ingreso/', views.marcar_ingreso, name='marcar_ingreso'),
    path('preview-imagen/', views.preview_imagen_final, name='preview_imagen'),

    path('login/', auth_views.LoginView.as_view(template_name='cliente/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),

    path("importar_excel/", views.importar_excel, name="importar_excel"),
    path('registro/', views.registro_participante, name='registro_participante'),
    path('cliente/registro_participante/', views.registro_participante, name='registro_participante_cliente'),

    path('participante/actualizar/<int:pk>/', views.actualizar_participante_previa, name='actualizar_participante_previa'),
    path('participante/eliminar/<int:pk>/', views.eliminar_participante_previa, name='eliminar_participante_previa'),

    path("participante/<str:cod_part>/enviar_whatsapp_qr/", views.enviar_whatsapp_qr, name="enviar_whatsapp_qr"),
    path('export/excel/', views.exportar_excel_previo, name='exportar_excel_previo'),
    path('export/pdf/', views.exportar_pdf_previo, name='exportar_pdf_previo'),
    path('participante/validar/<uuid:token>/', views.validar_entrada_previo, name='validar_entrada_previo'),
    path('participantes/enviar_todos_whatsapp/', views.enviar_todos_whatsapp, name='enviar_todos_whatsapp'),
    path("enviar_masivo/", views.enviar_masivo, name="enviar_masivo"),
    path('participantes/<int:participante_id>/voucher/', views.subir_voucher, name='subir_voucher'),

    # otras rutas...
    path('check-admin-masivo/', views.check_admin_masivo, name='check_admin_masivo'),
    path('check-contabilidad-masivo/', views.check_contabilidad_masivo, name='check_contabilidad_masivo'),
]
