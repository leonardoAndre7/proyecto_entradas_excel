from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Evento, PerfilUsuario

class EventoPermissionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Solo comprobar accesos autenticados
        if request.user.is_authenticated:
            if 'evento_id' in view_kwargs:
                try:
                    evento_id = view_kwargs['evento_id']
                    evento = get_object_or_404(Evento, pk=evento_id)
                    
                    # Cargar el perfil de rol del usuario
                    perfil, _ = PerfilUsuario.objects.get_or_create(
                        user=request.user, 
                        defaults={'rol': 'SUPERADMIN' if request.user.is_superuser else 'REGISTRADOR'}
                    )
                    
                    # Impedir acceso si el usuario no es superadmin ni tiene el evento asignado
                    if perfil.rol != 'SUPERADMIN' and evento not in perfil.eventos.all():
                        messages.error(request, "Acceso restringido: No tienes autorización para gestionar este evento.")
                        return redirect('dashboard_eventos')
                except Exception:
                    pass
        return None
