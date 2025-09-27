# gestion/proveedores/views.py
from rest_framework import viewsets
from .models import Proveedor
from .serializers import ProveedorSerializer
from rest_framework.permissions import IsAuthenticated

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated]
    
