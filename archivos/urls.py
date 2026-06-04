# gestion/backend/archivos/urls.py

from django.urls import path

from rest_framework.routers import DefaultRouter

from .views import (
    TipoArchivoViewSet,
    ArchivoViewSet,
    ArchivoRelacionViewSet,
)

# Catálogos secundarios siguen por router (sus prefijos no colisionan con
# el detalle <int:pk> del recurso principal, que sólo matchea enteros).
router = DefaultRouter()

router.register(
    r'tipos-archivo',
    TipoArchivoViewSet,
    basename='tipo-archivo',
)

router.register(
    r'relaciones',
    ArchivoRelacionViewSet,
    basename='archivo-relacion',
)

# Recurso principal mapeado EXPLÍCITAMENTE sobre la raíz del include
# ("api/archivos/"), para evitar el doble namespace /archivos/archivos/.
#   GET    /api/archivos/           → listado
#   POST   /api/archivos/upload/    → subida (FileService.upload, punto único)
#   GET    /api/archivos/{id}/      → detalle
#   DELETE /api/archivos/{id}/      → soft-delete
# NOTA: no se mapea POST sobre la raíz → crear por ahí devuelve 405 solo.
urlpatterns = [
    path(
        "",
        ArchivoViewSet.as_view({"get": "list"}),
        name="archivo-list",
    ),
    path(
        "upload/",
        ArchivoViewSet.as_view({"post": "upload_simple"}),
        name="archivo-upload",
    ),
    path(
        "upload-multiple/",
        ArchivoViewSet.as_view({"post": "upload_multiple"}),
        name="archivo-upload-multiple",
    ),
    path(
        "<int:pk>/",
        ArchivoViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="archivo-detail",
    ),
    *router.urls,
]
