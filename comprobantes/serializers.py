# gestion/comprobantes/serializers.py
from rest_framework import serializers
from .models import Comprobante

class ComprobanteSerializer(serializers.ModelSerializer):
    numero = serializers.IntegerField(required=False, read_only=True)  # Generado automáticamente

    class Meta:
        model = Comprobante
        fields = [
            'id', 'tipo', 'serie', 'numero', 'numero_inicial', 'numero_final', 'numero_comienzo'
        ]
        read_only_fields = ['numero']  # Solo numero es read_only

    def validate(self, data):
        # Validar que tipo sea "PRES" (fijo por ahora)
        if data.get('tipo') and data.get('tipo') != "PRES":
            raise serializers.ValidationError("El tipo debe ser 'PRES' (Presupuesto).")

        # Validar rango
        numero_inicial = data.get('numero_inicial')
        numero_final = data.get('numero_final')
        numero_comienzo = data.get('numero_comienzo')
        if numero_inicial is not None and numero_final is not None and numero_comienzo is not None:
            if numero_comienzo < numero_inicial or numero_comienzo > numero_final:
                raise serializers.ValidationError("El numero_comienzo debe estar dentro del rango de numero_inicial y numero_final.")
            if numero_final < numero_inicial:
                raise serializers.ValidationError("El numero_final no puede ser menor que numero_inicial.")
        return data

    def create(self, validated_data):
        return Comprobante.objects.create(**validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)