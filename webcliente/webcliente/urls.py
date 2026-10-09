"""
URL configuration for webcliente project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from cliente import views, puerta
from lotes import views as lotes_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_redirect, name='index'),
    path('nexo/', views.nexo_landing, name='nexo_landing'),
    path('nexo/track-event/', views.nexo_track_event, name='nexo_track_event'),
    path('participantes/', include('cliente.urls')),
    path('lotes/', include('lotes.urls')),
    # Atajos raíz para fácil acceso
    path('plano/', lotes_views.ver_plano,         name="plano"),        # admin
    path('mapa/',  lotes_views.ver_mapa_publico,  name="mapa_publico"), # clientes

    # 🚪 App de puerta (PWA de escaneo sin login de usuario)
    path('puerta/', puerta.puerta_app, name='puerta_app'),
    path('puerta/manifest.webmanifest', puerta.puerta_manifest, name='puerta_manifest'),
    path('puerta/sw.js', puerta.puerta_sw, name='puerta_sw'),
    path('puerta/admin/', puerta.puerta_panel, name='puerta_panel'),
    path('puerta/api/acceso/', puerta.puerta_acceso, name='puerta_acceso'),
    path('puerta/api/estado/', puerta.puerta_estado, name='puerta_estado'),
    path('puerta/api/validar/', puerta.puerta_validar, name='puerta_validar'),

    # 🔌 API REST — sin autenticación de sesión, protegida por X-API-Key
    path('api/registrar-participante/', views.api_registrar_participante, name='api_registrar_participante'),

    # 🔐 Google OAuth2 — rutas en raíz para coincidir con Google Cloud Console
    # Google Console tiene: http://localhost:8000/google/callback/
    #                        https://ede-evento.com/google/callback/
    path('google/auth/', views.google_auth_inicio, name='google_auth_inicio_root'),
    path('google/callback/', views.google_auth_callback, name='google_auth_callback_root'),
]
# Servir archivos media en cualquier modo (DEBUG o producción)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
