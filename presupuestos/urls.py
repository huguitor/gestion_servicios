# gestion/presupuestos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PresupuestoViewSet, PresupuestoAdjuntoViewSet

router = DefaultRouter()
router.register(r'', PresupuestoViewSet)

# 👇 CREAR router para adjuntos
adjuntos_router = DefaultRouter()
adjuntos_router.register(r'adjuntos', PresupuestoAdjuntoViewSet, basename='presupuesto-adjuntos')

urlpatterns = [
    path('', include(router.urls)),
    
    # Rutas anidadas para adjuntos
    path('<int:presupuesto_pk>/', include(adjuntos_router.urls)),
    
    # Ruta para tipos disponibles
    path('adjuntos/tipos/', 
         PresupuestoAdjuntoViewSet.as_view({'get': 'tipos_disponibles'}), 
         name='presupuesto-adjuntos-tipos'),
]