# sistema_general/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponseRedirect
from rest_framework.authtoken.views import obtain_auth_token
from django.conf import settings
from django.views.static import serve


# Función para redirigir CUALQUIER ruta al admin
def redirect_to_admin(request):
    return HttpResponseRedirect('/admin/')


urlpatterns = [
    # Redirige la raíz '/' al admin
    path('', redirect_to_admin, name='root_redirect'),
   
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/token/', obtain_auth_token, name='api_token'),
   
    # 👇 CONFIGURACIÓN GLOBAL (BASE DEL SISTEMA)
    path('configuracion/', include('configuracion.urls')),
    # 👇 APPS DE NEGOCIO
    path('clientes/', include('clientes.urls')),
    path('proveedores/', include('proveedores.urls')),
    path('productos/', include('productos.urls')),
    path('categorias/', include('categorias.urls')),
    path('marcas/', include('marcas.urls')),
    path('presupuestos/', include('presupuestos.urls')),
    path('remitos/', include('remitos.urls')),
    path('impuestos/', include('impuestos.urls')),
    path('comprobantes/', include('comprobantes.urls')),
]


# ========== SERVIR ARCHIVOS MEDIA - SIEMPRE ==========
# ✅ CAMBIADO: Ahora sirve media EN AMBOS MODOS (desarrollo y .exe)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]
# =====================================================


# ✅ CAPTURA CUALQUIER OTRA RUTA NO DEFINIDA Y REDIRIGE AL ADMIN
# (esto va ÚLTIMO, después de media)
urlpatterns += [
    re_path(r'^.*$', redirect_to_admin),
]