# gestion/proveedores/serializers.py
from rest_framework import serializers
from .models import Proveedor

class ProveedorSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='__str__', read_only=True)
    class Meta:
        model = Proveedor
        fields = [
            'id', 'tipo', 'nombre', 'documento', 'condicion_iva',
            'telefono', 'email', 'direccion', 'ciudad', 'provincia', 'pais',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = ['creado', 'actualizado', 'display_name']

    def validate_documento(self, value):
        if value and (len(value) not in [8, 11] or not value.isdigit()):
            raise serializers.ValidationError("El documento debe tener 8 (DNI) o 11 (CUIT) dígitos numéricos.")
        return value

    def validate_nombre(self, value):
        if not value.strip():
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value