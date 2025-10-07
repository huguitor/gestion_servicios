# gestion/presupuestos/views.py
from rest_framework import viewsets
from .models import Presupuesto
from .serializers import PresupuestoSerializer
from rest_framework.permissions import IsAuthenticated

class PresupuestoViewSet(viewsets.ModelViewSet):
    queryset = Presupuesto.objects.all()
    serializer_class = PresupuestoSerializer
    permission_classes = [IsAuthenticated]
    
    # 👇 AGREGÁ ESTE MÉTODO
    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)