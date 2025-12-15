# gestion/proveedores/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProveedorViewSet

router = DefaultRouter()
router.register(r'', ProveedorViewSet)
urlpatterns = [
    path('', include(router.urls))]
