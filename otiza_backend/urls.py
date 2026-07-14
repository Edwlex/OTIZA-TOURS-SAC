from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView  
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect raíz a login
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    
    # Incluir todas las URLs de core (login, dashboard, etc.)
    path('', include('core.urls')),
]

# Servir archivos estáticos en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)