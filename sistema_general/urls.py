# gestion/backend/sistema_general/urls.py

from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse
from django.views.static import serve
from django.conf import settings

from rest_framework.authtoken.views import obtain_auth_token

from .admin_auth import AdminLoginView


# ==========================================================
# HELPERS
# ==========================================================

def modulo_activo(nombre):
    """
    Consulta si un módulo está habilitado desde settings.py

    Ejemplo:

    MODULO_PEDIDOS=True
    MODULO_PRESUPUESTOS=False
    """

    return getattr(
        settings,
        nombre,
        False
    )


def api_root(request):
    """
    Endpoint raíz del backend.
    """

    return JsonResponse({
        "status": "ok",
        "service": "Gestion API",
        "empresa": settings.EMPRESA_NOMBRE,
        "admin": "/admin/",
        "token": "/api/token/",

        "modulos": {
            "clientes": settings.MODULO_CLIENTES,
            "productos": settings.MODULO_PRODUCTOS,
            "presupuestos": settings.MODULO_PRESUPUESTOS,
            "pedidos": settings.MODULO_PEDIDOS,
            "pedidos_internos": settings.MODULO_PEDIDOS_INTERNOS,
            "remitos": settings.MODULO_REMITOS,
            "stock": settings.MODULO_STOCK,
            "archivos": True,
        }
    })


# ==========================================================
# BASE
# ==========================================================

urlpatterns = [

    # API ROOT
    path(
        "",
        api_root,
        name="api_root"
    ),

    # DJANGO ADMIN
    path(
        "admin/",
        admin.site.urls
    ),

    # DRF LOGIN
    path(
        "api-auth/",
        include("rest_framework.urls")
    ),

    # TOKEN AUTH
    path(
        "api/token/",
        obtain_auth_token,
        name="api_token"
    ),

    # LOGIN ADMIN PERSONALIZADO
    path(
        "api/admin/login/",
        AdminLoginView.as_view(),
        name="admin_login"
    ),

]


# ==========================================================
# MÓDULOS SIEMPRE ACTIVOS
# ==========================================================

urlpatterns += [

    path(
        "api/configuracion/",
        include("configuracion.urls")
    ),

    path(
        "api/impuestos/",
        include("impuestos.urls")
    ),

    path(
        "api/comprobantes/",
        include("comprobantes.urls")
    ),

    # NUEVO REPOSITORIO CENTRAL DE ARCHIVOS
    path(
        "api/archivos/",
        include("archivos.urls")
    ),

    path(
        "api/personal/",
        include("personal.api.urls")
    ),

    path(
        "api/cobranzas/",
        include("cobranzas.urls")
    ),

]


# ==========================================================
# CLIENTES
# ==========================================================

if modulo_activo("MODULO_CLIENTES"):

    urlpatterns += [

        path(
            "api/clientes/",
            include("clientes.urls")
        ),

        path(
            "api/web-clientes/",
            include("web_clientes.urls")
        ),

    ]


# ==========================================================
# PRODUCTOS
# ==========================================================

if modulo_activo("MODULO_PRODUCTOS"):

    urlpatterns += [

        path(
            "api/productos/",
            include("productos.urls")
        ),

        path(
            "api/categorias/",
            include("categorias.urls")
        ),

        path(
            "api/marcas/",
            include("marcas.urls")
        ),

        path(
            "api/proveedores/",
            include("proveedores.urls")
        ),

    ]


# ==========================================================
# PRESUPUESTOS
# ==========================================================

if modulo_activo("MODULO_PRESUPUESTOS"):

    urlpatterns += [

        path(
            "api/presupuestos/",
            include("presupuestos.urls")
        ),

    ]


# ==========================================================
# PEDIDOS
# ==========================================================

if modulo_activo("MODULO_PEDIDOS"):

    urlpatterns += [

        path(
            "api/pedidos/",
            include("pedidos.urls")
        ),

    ]


# ==========================================================
# PEDIDOS INTERNOS
# ==========================================================

if modulo_activo("MODULO_PEDIDOS_INTERNOS"):

    urlpatterns += [

        path(
            "api/pedidos-internos/",
            include("pedidos_internos.api.urls")
        ),

    ]


# ==========================================================
# REMITOS
# ==========================================================

if modulo_activo("MODULO_REMITOS"):

    urlpatterns += [

        path(
            "api/remitos/",
            include("remitos.urls")
        ),

    ]


# ==========================================================
# WEB PÚBLICA
# ==========================================================

if modulo_activo("MODULO_WEB_PUBLICA"):

    urlpatterns += [

        path(
            "api/web/",
            include("web_publica.urls")
        ),

    ]


# ==========================================================
# BACKUP
# ==========================================================

if modulo_activo("MODULO_BACKUP"):

    urlpatterns += [

        path(
            "api/backup/",
            include("backup.urls")
        ),

    ]


# ==========================================================
# MEDIA FILES
# ==========================================================

urlpatterns += [

    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {
            "document_root": settings.MEDIA_ROOT,
        }
    ),

]
