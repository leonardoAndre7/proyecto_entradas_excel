from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 🏠 Redirección de Inicio
    path('', views.home_redirect, name='index'),
    path('participantes/', views.home_redirect, name='lista'),
    path('participantes/agregar/', views.home_redirect, name='participante_agregar'),
    path('participantes/editar/<int:pk>/editar', views.home_redirect, name='participante_editar'),
    path('participantes/eliminar/<int:pk>/eliminar', views.home_redirect, name='participante_eliminar'),
    path('confirmar-pago/<int:pk>/', views.home_redirect, name='confirmar_pago'),
    
    # 🏢 Panel de Control General de Eventos (SaaS Dashboard)
    path('dashboard/', views.dashboard_eventos, name='dashboard_eventos'),
    path('eventos/crear/', views.evento_crear_editar, name='evento_crear'),
    path('eventos/editar/<int:pk>/', views.evento_crear_editar, name='evento_editar'),
    path('eventos/eliminar/<int:pk>/', views.evento_eliminar, name='evento_eliminar'),
    
    # 🎟️ Vistas de Participantes Filtradas por Evento
    path('eventos/<int:evento_id>/participantes/', views.ParticipanteListView.as_view(), name='participante_lista'),
    path('eventos/<int:evento_id>/previa/', views.registro_participante, name='registro_participante'),
    path('eventos/<int:evento_id>/participantes/agregar/', views.ParticipanteCreateView.as_view(), name='participante_agregar'),
    path('eventos/<int:evento_id>/participantes/editar/<int:pk>/', views.ParticipanteUpdateView.as_view(), name='participante_editar'),
    path('eventos/<int:evento_id>/participantes/eliminar/<int:pk>/', views.ParticipanteDeleteView.as_view(), name='participante_eliminar'),
    
    path('eventos/<int:evento_id>/exportar-excel/', views.exportar_excel, name='exportar_excel'),
    path('eventos/<int:evento_id>/importar-excel/', views.importar_excel, name='importar_excel'),
    path('eventos/<int:evento_id>/enviar-masivo/', views.enviar_masivo, name='enviar_masivo'),
    
    path('eventos/<int:evento_id>/check-admin-masivo/', views.check_admin_masivo, name='check_admin_masivo'),
    path('eventos/<int:evento_id>/check-contabilidad-masivo/', views.check_contabilidad_masivo, name='check_contabilidad_masivo'),
    path('eventos/<int:evento_id>/confirmar-pago/<int:pk>/', views.confirmar_pago, name='confirmar_pago'),
    path('eventos/<int:evento_id>/marcar-ingreso/<int:pk>/', views.marcar_ingreso, name='marcar_ingreso'),
    path('eventos/<int:evento_id>/reenviar/<int:pk>/', views.reenviar_correo, name='reenviar_correo'),
    path('eventos/<int:evento_id>/limpiar-historial/', views.limpiar_historial, name='limpiar_historial'),
    
    # Previa del despertar
    path('eventos/<int:evento_id>/previa/convertir/<int:pk>/', views.convertir_previa_a_participante, name='convertir_previa'),
    path('eventos/<int:evento_id>/previa/marcar-ingreso/<int:pk>/', views.marcar_ingreso_previa, name='marcar_ingreso_previa'),
    path('eventos/<int:evento_id>/previa/actualizar/<int:pk>/', views.actualizar_participante_previa, name='actualizar_participante_previa'),
    path('eventos/<int:evento_id>/previa/eliminar/<int:pk>/', views.eliminar_participante_previa, name='eliminar_participante_previa'),
    path('eventos/<int:evento_id>/previa/enviar-whatsapp-qr/<str:cod_part>/', views.enviar_whatsapp_qr, name='enviar_whatsapp_qr'),
    path('eventos/<int:evento_id>/previa/enviar-todos/', views.enviar_todos_whatsapp, name='enviar_todos_whatsapp'),
    path('eventos/<int:evento_id>/previa/exportar-excel/', views.exportar_excel_previo, name='exportar_excel_previo'),
    path('eventos/<int:evento_id>/previa/exportar-pdf/', views.exportar_pdf_previo, name='exportar_pdf_previo'),
    path('eventos/<int:evento_id>/previa/limpiar-historial/', views.limpiar_historial_previa, name='limpiar_historial_previa'),
    
    # 🔒 Validación QR (Cámara nativa - Mobile friendly redirect)
    path('validar/<str:token>/', views.validar_entrada, name='validar_entrada'),
    path('previa/validar/<uuid:token>/', views.validar_entrada_previo, name='validar_entrada_previo'),
    
    # 🔐 Auth
    path('login/', auth_views.LoginView.as_view(template_name='cliente/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # 👥 Gestión de Usuarios
    path('usuarios/', views.usuario_lista, name='usuario_lista'),
    path('usuarios/crear/', views.usuario_crear, name='usuario_crear'),
    path('usuarios/editar/<int:pk>/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/eliminar/<int:pk>/', views.usuario_eliminar, name='usuario_eliminar'),

    # 👤 Perfil propio del usuario
    path('mi-cuenta/', views.mi_cuenta, name='mi_cuenta'),

    # 🔐 Google OAuth2 — Conexión de Gmail para envío de entradas
    path('google/auth/', views.google_auth_inicio, name='google_auth_inicio'),
    path('google/callback/', views.google_auth_callback, name='google_auth_callback'),
    path('google/desconectar/', views.google_desconectar, name='google_desconectar'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
