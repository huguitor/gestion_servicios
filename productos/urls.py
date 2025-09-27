# gestion/productos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductoViewSet, ServicioViewSet

router = DefaultRouter()
router.register(r'productos', ProductoViewSet) # http://127.0.0.1:8000/productos/productos/
router.register(r'servicios', ServicioViewSet) # http://127.0.0.1:8000/productos/servicios/
urlpatterns = [
    path('', include(router.urls)),
]   
