# gestion/comprobantes/serializers.py
from rest_framework import serializers
from .models import Comprobante


class ComprobanteSerializer(serializers.ModelSerializer):
    numero = serializers.IntegerField(required=False, read_only=True)
    numeros_disponibles = serializers.IntegerField(read_only=True)
    porcentaje_usado = serializers.FloatField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = Comprobante
        fields = [
            'id', 'tipo', 'tipo_display', 'serie', 'numero', 
            'numero_inicial', 'numero_final', 'proximo_numero',
            'numeros_disponibles', 'porcentaje_usado'
        ]
        read_only_fields = ['numero']

    def validate(self, data):
        # ⭐ CAMBIADO: Aceptar tanto PRES como REMI
        tipo = data.get('tipo')
        if tipo and tipo not in ["PRES", "REMI"]:
            raise serializers.ValidationError({
                "tipo": "El tipo debe ser 'PRES' (Presupuesto) o 'REMI' (Remito Interno)."
            })

        # ⭐ CAMBIADO: numero_comienzo → proximo_numero
        numero_inicial = data.get('numero_inicial')
        numero_final = data.get('numero_final')
        proximo_numero = data.get('proximo_numero')
        
        if numero_inicial is not None and numero_final is not None and proximo_numero is not None:
            if proximo_numero < numero_inicial or proximo_numero > numero_final:
                raise serializers.ValidationError({
                    "proximo_numero": "Debe estar dentro del rango de numero_inicial y numero_final."
                })
            if numero_final < numero_inicial:
                raise serializers.ValidationError({
                    "numero_final": "No puede ser menor que numero_inicial."
                })
        
        return data

    def create(self, validated_data):
        return Comprobante.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # No permitir cambiar el tipo
        if 'tipo' in validated_data and instance.tipo != validated_data['tipo']:
            raise serializers.ValidationError({
                "tipo": "No se puede cambiar el tipo de comprobante."
            })
        
        return super().update(instance, validated_data)