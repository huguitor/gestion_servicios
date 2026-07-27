# gestion/backend/pedidos_internos/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardPedidosInternosView,
    MisSectoresView,
    PedidoInternoViewSet,
    SectorViewSet,
)

router = DefaultRouter()
router.register(r'sectores', SectorViewSet, basename='sectores-internos')
router.register(r'pedidos', PedidoInternoViewSet, basename='pedidos-internos')

urlpatterns = [
    path('mis-sectores/', MisSectoresView.as_view(), name='pedidos-internos-mis-sectores'),
    path('dashboard/', DashboardPedidosInternosView.as_view(), name='pedidos-internos-dashboard'),
    path('', include(router.urls)),
]
