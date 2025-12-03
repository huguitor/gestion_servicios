# gestion/impuestos/views.py
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Impuesto
from .serializers import ImpuestoSerializer
from rest_framework.permissions import IsAuthenticated


class ImpuestoViewSet(viewsets.ModelViewSet):
    queryset = Impuesto.objects.all()
    serializer_class = ImpuestoSerializer
    permission_classes = [IsAuthenticated]
    
    # Agregar filtros y búsqueda
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # Filtros por campos exactos
    filterset_fields = ['tipo']
    
    # Campos de búsqueda
    search_fields = ['nombre', 'display_name']
    
    # Ordenamiento por defecto
    ordering_fields = ['nombre', 'porcentaje', 'tipo']
    ordering = ['nombre']
    