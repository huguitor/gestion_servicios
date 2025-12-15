# gestion/comprobantes/views.py (igual)
from rest_framework import viewsets
from .models import Comprobante
from .serializers import ComprobanteSerializer
from rest_framework.permissions import IsAuthenticated

class ComprobanteViewSet(viewsets.ModelViewSet):
    queryset = Comprobante.objects.all()
    serializer_class = ComprobanteSerializer
    permission_classes = [IsAuthenticated]