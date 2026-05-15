# gestion/remitos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RemitoViewSet, ItemRemitoViewSet, RemitoAdjuntoViewSet

router = DefaultRouter()
router.register(r'', RemitoViewSet, basename='remito')
# Items lookup separado (mantenido por compatibilidad con el Tkinter)
router.register(r'items', ItemRemitoViewSet, basename='itemremito')

# Tanda 5: router anidado para adjuntos, mismo patrón que presupuestos.
# Hasta ahora `RemitoAdjuntoViewSet` estaba definido pero no registrado, por lo
# que el Tkinter no podía hacer DELETE de adjuntos individuales.
adjuntos_router = DefaultRouter()
adjuntos_router.register(r'adjuntos', RemitoAdjuntoViewSet, basename='remito-adjuntos')

urlpatterns = [
    path('', include(router.urls)),
    # /api/remitos/{remito_pk}/adjuntos/             (GET list, POST create)
    # /api/remitos/{remito_pk}/adjuntos/{pk}/        (GET, PUT, PATCH, DELETE)
    path('<int:remito_pk>/', include(adjuntos_router.urls)),
]
