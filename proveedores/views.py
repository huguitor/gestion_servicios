# gestion/proveedores/views.py
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from .models import Proveedor
from .serializers import ProveedorSerializer


class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['nombre', 'documento', 'email']
    filterset_fields = ['tipo', 'condicion_iva', 'activo']

