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
        """
        Valida:
        - DNI: 8 dígitos (solo físicos)
        - CUIT: 11 dígitos con prefijo válido según tipo
        """
        # Obtener el tipo de persona (física/jurídica)
        tipo = None
        
        # Si estamos actualizando una instancia existente
        if self.instance:
            tipo = self.instance.tipo
        # Si estamos creando un nuevo proveedor
        elif 'tipo' in self.initial_data:
            tipo = self.initial_data.get('tipo')
        
        # Si no hay documento, no hay problema
        if not value:
            return value
        
        # Si no tenemos tipo, no podemos validar completamente
        if not tipo:
            raise serializers.ValidationError(
                "No se pudo determinar el tipo de persona para validar el documento."
            )
        
        # Validar que solo contenga dígitos
        if not value.isdigit():
            raise serializers.ValidationError("El documento debe contener solo dígitos.")
        
        # Validar DNI (8 dígitos)
        if len(value) == 8:
            if tipo != "fisica":
                raise serializers.ValidationError(
                    "Los DNI de 8 dígitos solo son válidos para Personas Físicas."
                )
            return value
        
        # Validar CUIT (11 dígitos)
        if len(value) == 11:
            prefijo = value[:2]
            
            # Prefijos válidos según AFIP
            prefijos_fisica = {"20", "23", "24", "27"}
            prefijos_juridica = {"30", "33", "34"}
            
            if tipo == "fisica" and prefijo not in prefijos_fisica:
                raise serializers.ValidationError(
                    f"Para Personas Físicas, el CUIT debe comenzar con {', '.join(sorted(prefijos_fisica))}. "
                    f"Prefijo ingresado: {prefijo}"
                )
            
            if tipo == "juridica" and prefijo not in prefijos_juridica:
                raise serializers.ValidationError(
                    f"Para Personas Jurídicas, el CUIT debe comenzar con {', '.join(sorted(prefijos_juridica))}. "
                    f"Prefijo ingresado: {prefijo}"
                )
            
            # Aquí podrías agregar validación del dígito verificador si lo necesitas
            # if not self._validar_digito_verificador_cuit(value):
            #     raise serializers.ValidationError("CUIT inválido (dígito verificador incorrecto).")
            
            return value
        
        # Longitud incorrecta
        raise serializers.ValidationError(
            "El documento debe tener 8 dígitos (DNI) o 11 dígitos (CUIT). "
            f"Longitud actual: {len(value)} dígitos."
        )

    def validate_nombre(self, value):
        """Valida que el nombre no esté vacío."""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value.strip()

    # Método opcional para validar dígito verificador del CUIT
    # def _validar_digito_verificador_cuit(self, cuit):
    #     """
    #     Valida el dígito verificador de un CUIT.
    #     Algoritmo según AFIP.
    #     """
    #     if len(cuit) != 11:
    #         return False
        
    #     coeficientes = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    #     cuit_numeros = [int(d) for d in cuit]
        
    #     # Calcular suma ponderada
    #     suma = sum(cuit_numeros[i] * coeficientes[i] for i in range(10))
        
    #     # Calcular dígito verificador
    #     resto = suma % 11
    #     if resto == 0:
    #         digito_verificador = 0
    #     elif resto == 1:
    #         # Para género masculino (20) se usa 9, para femenino (27) se usa 4
    #         if cuit[:2] == "20":
    #             digito_verificador = 9
    #         elif cuit[:2] == "27":
    #             digito_verificador = 4
    #         else:
    #             return False
    #     else:
    #         digito_verificador = 11 - resto
        
    #     return cuit_numeros[10] == digito_verificador