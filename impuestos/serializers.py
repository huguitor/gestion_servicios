# gestion/impuestos/serializers.py
from rest_framework import serializers
from .models import Impuesto

class ImpuestoSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Impuesto
        fields = ['id', 'nombre', 'porcentaje', 'tipo', 'creado', 'actualizado', 'display_name']
        read_only_fields = ['creado', 'actualizado', 'display_name']