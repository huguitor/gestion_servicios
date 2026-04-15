# gestion/productos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductoViewSet,
    ServicioViewSet,
    CatalogoMercaderiaListView,
    ProductoWebDetailView,
    CatalogoServiciosListView,
    ServicioWebDetailView,
)

router = DefaultRouter()
router.register(r'productos', ProductoViewSet) # http://127.0.0.1:8000/productos/productos/
router.register(r'servicios', ServicioViewSet) # http://127.0.0.1:8000/productos/servicios/
urlpatterns = [
    path('', include(router.urls)),

    # Web pública
    path('web/catalogo/mercaderia/', CatalogoMercaderiaListView.as_view(), name='web-catalogo-mercaderia'),
    path('web/catalogo/servicios/', CatalogoServiciosListView.as_view(), name='web-catalogo-servicios'),
    path('web/productos/<slug:slug>/', ProductoWebDetailView.as_view(), name='web-producto-detalle'),
    path('web/servicios/<slug:slug>/', ServicioWebDetailView.as_view(), name='web-servicio-detalle'),
]