# gestion/impuestos/views.py
from rest_framework import viewsets
from .models import Impuesto
from .serializers import ImpuestoSerializer 
from rest_framework.permissions import IsAuthenticated

class ImpuestoViewSet(viewsets.ModelViewSet):
    queryset = Impuesto.objects.all()
    serializer_class = ImpuestoSerializer
    permission_classes = [IsAuthenticated]
    