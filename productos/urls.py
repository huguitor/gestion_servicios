# gestion/backend/productos/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductoViewSet,
    ServicioViewSet,
    CatalogoMercaderiaListView,
    CatalogoMercaderiaClienteListView,
    ProductoWebDetailView,
    ProductoWebClienteDetailView,
    CatalogoServiciosListView,
    CatalogoServiciosClienteListView,
    ServicioWebDetailView,
    ServicioWebClienteDetailView,
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
    path('web/catalogo/mercaderia-cliente/', CatalogoMercaderiaClienteListView.as_view(), name='web-catalogo-mercaderia-cliente'),
    path('web/productos-cliente/<slug:slug>/', ProductoWebClienteDetailView.as_view(), name='web-producto-cliente-detalle'),
    path('web/catalogo/servicios-cliente/', CatalogoServiciosClienteListView.as_view(), name='web-catalogo-servicios-cliente'),
    path('web/servicios-cliente/<slug:slug>/', ServicioWebClienteDetailView.as_view(), name='web-servicio-cliente-detalle'),
]