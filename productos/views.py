# gestion/productos/views.py
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Producto, Servicio
from .serializers import (
    ProductoSerializer,
    ServicioSerializer,
    ProductoWebPublicoSerializer,
    ProductoWebDetalleSerializer,
    ServicioWebPublicoSerializer,
    ServicioWebDetalleSerializer,
)

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        """Pasar el request al serializer para construir URLs absolutas"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.all()
    serializer_class = ServicioSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        """Pasar el request al serializer para construir URLs absolutas"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context



class CatalogoMercaderiaListView(generics.ListAPIView):
    serializer_class = ProductoWebPublicoSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Producto.objects.filter(
            activo=True,
            publicado_web=True
        ).order_by("orden_web", "nombre")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class ProductoWebDetailView(generics.RetrieveAPIView):
    serializer_class = ProductoWebDetalleSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return Producto.objects.filter(
            activo=True,
            publicado_web=True
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class CatalogoServiciosListView(generics.ListAPIView):
    serializer_class = ServicioWebPublicoSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Servicio.objects.filter(
            activo=True,
            publicado_web=True
        ).order_by("orden_web", "nombre")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class ServicioWebDetailView(generics.RetrieveAPIView):
    serializer_class = ServicioWebDetalleSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return Servicio.objects.filter(
            activo=True,
            publicado_web=True
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
    