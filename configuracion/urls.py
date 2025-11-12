# gestion/configuracion/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConfiguracionGlobalViewSet

# 👇 ROUTER PARA LA API
router = DefaultRouter()
router.register(r'configuracion', ConfiguracionGlobalViewSet, basename='configuracion')

urlpatterns = [
    path('', include(router.urls)),
]