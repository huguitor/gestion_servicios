# gestion_servicios/pedidos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PedidoViewSet

router = DefaultRouter()
router.register(r'', PedidoViewSet, basename='pedidos')

urlpatterns = [
    path('', include(router.urls)),
]