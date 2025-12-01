# gestion/productos/views.py
from rest_framework import viewsets
from .models import Producto, Servicio
from .serializers import ProductoSerializer, ServicioSerializer
from rest_framework.permissions import IsAuthenticated


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

    