# gestion/backend/pedidos_internos/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SectorViewSet, PedidoInternoViewSet

router = DefaultRouter()
router.register(r'sectores', SectorViewSet, basename='sectores-internos')
router.register(r'pedidos', PedidoInternoViewSet, basename='pedidos-internos')

urlpatterns = [
    path('', include(router.urls)),
]
