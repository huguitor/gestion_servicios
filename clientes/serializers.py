# gestion/clientes/serializers.py
from rest_framework import serializers
from .models import Cliente

class ClienteSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Cliente
        fields = [
            'id', 'tipo', 'nombre', 'apellido', 'documento', 'condicion_iva',
            'telefono', 'email', 'direccion', 'ciudad', 'provincia', 'pais',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = ['creado', 'actualizado', 'display_name']

    def validate(self, data):
        tipo = data.get('tipo', self.instance.tipo if self.instance else 'fisica')
        if tipo == 'fisica' and not data.get('apellido'):
            raise serializers.ValidationError("El apellido es obligatorio para Persona Física.")
        if tipo == 'juridica' and data.get('apellido'):
            raise serializers.ValidationError("El apellido no debe proporcionarse para Persona Jurídica.")
        return data

    def validate_documento(self, value):
        if value and (len(value) not in [8, 11] or not value.isdigit()):
            raise serializers.ValidationError("El documento debe tener 8 (DNI) o 11 (CUIT) dígitos numéricos.")
        return value

    def validate_nombre(self, value):
        if not value.strip():
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value