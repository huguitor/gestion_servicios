# gestion/backend/archivos/urls.py

from rest_framework.routers import DefaultRouter

from .views import (
    TipoArchivoViewSet,
    ArchivoViewSet,
    ArchivoRelacionViewSet,
)

router = DefaultRouter()

router.register(
    r'tipos-archivo',
    TipoArchivoViewSet,
    basename='tipo-archivo'
)

router.register(
    r'archivos',
    ArchivoViewSet,
    basename='archivo'
)

router.register(
    r'relaciones',
    ArchivoRelacionViewSet,
    basename='archivo-relacion'
)

urlpatterns = router.urls