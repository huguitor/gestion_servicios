# sistema_general/urls.py
import os
from pathlib import Path

from django.contrib import admin
from django.urls import path, include, re_path
from django.http import FileResponse, HttpResponseNotFound
from rest_framework.authtoken.views import obtain_auth_token
from django.conf import settings
from django.views.static import serve


# ============================================================================
# SPA: servir el frontend buildeado (Vite → /var/www/web_frontend/dist).
# ============================================================================
#
# Estrategia: una sola vista que decide:
#   - Si el path coincide con un archivo real en dist/, lo sirve.
#   - Si no, devuelve dist/index.html — el SPA se encarga del routing del lado
#     del cliente.
#
# Las rutas /admin/, /api/, /api-auth/, /media/ tienen prioridad y se evalúan
# antes (Django prueba urlpatterns en orden).

WEB_DIST = Path(getattr(settings, 'WEB_DIST_DIR', '/var/www/web_frontend/dist'))


def spa(request, path: str = ''):
    """
    Servidor del SPA buildeado.

    Si el archivo existe en WEB_DIST, lo sirve. Si no, devuelve index.html
    para que React Router maneje la ruta. Defiende contra path traversal:
    el target resuelto debe estar bajo WEB_DIST.
    """
    if not WEB_DIST.exists():
        return HttpResponseNotFound(
            f"Frontend no buildeado todavía. "
            f"Corré 'npm run build' en /var/www/web_frontend/ "
            f"(o el servicio gestion-frontend.service)."
        )

    candidate = (WEB_DIST / path).resolve() if path else (WEB_DIST / 'index.html')
    try:
        candidate.relative_to(WEB_DIST.resolve())
    except ValueError:
        return HttpResponseNotFound('Not found.')

    if candidate.is_file():
        return FileResponse(open(candidate, 'rb'))
    # SPA fallback — cualquier ruta no matcheada por archivos reales devuelve
    # index.html para que React Router resuelva.
    index = WEB_DIST / 'index.html'
    if index.is_file():
        return FileResponse(open(index, 'rb'))
    return HttpResponseNotFound('Not found.')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/token/', obtain_auth_token, name='api_token'),

    # RUTAS DE API (con prefijo /api/)
    path('api/configuracion/', include('configuracion.urls')),
    path('api/clientes/', include('clientes.urls')),
    path('api/web-clientes/', include('web_clientes.urls')),
    path('api/proveedores/', include('proveedores.urls')),
    path('api/productos/', include('productos.urls')),
    path('api/categorias/', include('categorias.urls')),
    path('api/marcas/', include('marcas.urls')),
    path('api/presupuestos/', include('presupuestos.urls')),
    path('api/pedidos/', include('pedidos.urls')),
    path('api/remitos/', include('remitos.urls')),
    path('api/impuestos/', include('impuestos.urls')),
    path('api/comprobantes/', include('comprobantes.urls')),
    path('api/web/', include('web_publica.urls')),
    path('api/backup/', include('backup.urls')),

    # Las rutas legacy SIN PREFIJO (/clientes/, /presupuestos/, etc.) que usaba
    # el cliente Tkinter se removieron acá — chocaban con las rutas del SPA
    # (React Router también usa /clientes, /presupuestos, etc.).
    # El frontend web habla exclusivamente con /api/*.
]


# Servir archivos /media/ siempre (también en producción).
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]


# SPA al final — captura todo lo demás (root + rutas de React Router como
# /clientes, /presupuestos, /backup, etc., y los assets del bundle).
# El negative lookahead protege contra capturar rutas sin trailing slash
# que pertenecen al backend (admin, api, media, api-auth).
urlpatterns += [
    re_path(r'^$', spa),
    re_path(
        r'^(?!admin/|api/|api-auth/|media/|admin$|api$|api-auth$|media$)(?P<path>.+)$',
        spa,
    ),
]

