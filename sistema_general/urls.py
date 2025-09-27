# sistema_general/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),  # Login/logout para DRF
    path('api/token/', obtain_auth_token, name='api_token'),  # Obtener token
    path('clientes/', include('clientes.urls')),
    path('proveedores/', include('proveedores.urls')),
    path('productos/', include('productos.urls')),
    path('categorias/', include('categorias.urls')),
    path('marcas/', include('marcas.urls')),
    path('presupuestos/', include('presupuestos.urls')),
    path('impuestos/', include('impuestos.urls')),
    path('comprobantes/', include('comprobantes.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)