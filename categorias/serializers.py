# gestion/categorias/serializers.py
from rest_framework import serializers
from .models import Categoria

class CategoriaSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'descripcion', 'activo', 'creado', 'actualizado', 'display_name']
        read_only_fields = ['creado', 'actualizado', 'display_name']