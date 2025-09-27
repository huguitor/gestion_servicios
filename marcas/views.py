# gestion/marcas/views.py
from rest_framework import viewsets
from .models import Marca       
from .serializers import MarcaSerializer
from rest_framework.permissions import IsAuthenticated

class MarcaViewSet(viewsets.ModelViewSet):
    queryset = Marca.objects.all()
    serializer_class = MarcaSerializer
    permission_classes = [IsAuthenticated]
    
