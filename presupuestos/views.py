# gestion/presupuestos/views.py
from rest_framework import viewsets
from .models import Presupuesto 
from .serializers import PresupuestoSerializer
from rest_framework.permissions import IsAuthenticated

class PresupuestoViewSet(viewsets.ModelViewSet):
    queryset = Presupuesto.objects.all()
    serializer_class = PresupuestoSerializer
    permission_classes = [IsAuthenticated]  
    
