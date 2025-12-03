# gestion/impuestos/serializers.py
from rest_framework import serializers
from .models import Impuesto


class ImpuestoSerializer(serializers.ModelSerializer):
    # display_name ya NO es read-only
    
    class Meta:
        model = Impuesto
        fields = ['id', 'nombre', 'porcentaje', 'tipo', 'display_name', 'creado', 'actualizado']
        read_only_fields = ['creado', 'actualizado']  # ¡display_name YA NO está aquí!
        # Ahora display_name se puede editar desde la API