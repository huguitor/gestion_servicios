from rest_framework import serializers
from .models import Comprobante

class ComprobanteSerializer(serializers.ModelSerializer):
    # ⭐⭐ CAMPOS CALCULADOS (solo lectura)
    numeros_disponibles = serializers.IntegerField(read_only=True)
    numeros_usados = serializers.IntegerField(read_only=True)
    porcentaje_usado = serializers.FloatField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    esta_agotado = serializers.BooleanField(read_only=True)
    advertencia_rango = serializers.CharField(read_only=True)
    
    # ⭐⭐ CAMPOS PARA FORMATEO (solo lectura)
    formato_proximo = serializers.SerializerMethodField()
    formato_rango = serializers.SerializerMethodField()

    class Meta:
        model = Comprobante
        fields = [
            'id',
            'tipo',
            'tipo_display',
            'serie',
            'numero_inicial',
            'numero_final',
            'proximo_numero',
            
            # Campos calculados
            'numeros_disponibles',
            'numeros_usados',
            'porcentaje_usado',
            'esta_agotado',
            'advertencia_rango',
            
            # Campos formateados
            'formato_proximo',
            'formato_rango'
        ]
        read_only_fields = [
            'numeros_disponibles',
            'numeros_usados',
            'porcentaje_usado',
            'esta_agotado',
            'advertencia_rango',
            'formato_proximo',
            'formato_rango'
        ]

    def get_formato_proximo(self, obj):
        """Formato: PRÓXIMO: 000255"""
        return f"{obj.serie}-{obj.proximo_numero:06d}"

    def get_formato_rango(self, obj):
        """Formato: RANGO: 000001-000400"""
        return f"{obj.numero_inicial:06d}-{obj.numero_final:06d}"

    def validate(self, data):
        """
        Validación global del serializer
        
        Importante: Esta validación se ejecuta ANTES de guardar,
        tanto en creación como en actualización.
        """
        # Obtener valores (usar datos nuevos o existentes)
        tipo = data.get('tipo', self.instance.tipo if self.instance else None)
        serie = data.get('serie', self.instance.serie if self.instance else None)
        numero_inicial = data.get('numero_inicial', self.instance.numero_inicial if self.instance else None)
        numero_final = data.get('numero_final', self.instance.numero_final if self.instance else None)
        proximo_numero = data.get('proximo_numero', self.instance.proximo_numero if self.instance else None)

        # ⭐⭐ 1. Validar que no exista otro con mismo tipo+serie (excepto si es el mismo)
        if tipo and serie:
            queryset = Comprobante.objects.filter(tipo=tipo, serie=serie)
            
            # Si estamos actualizando, excluir este mismo registro
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise serializers.ValidationError({
                    "tipo": f"Ya existe una configuración para {tipo}-{serie}",
                    "serie": "Cada combinación tipo+serie debe ser única"
                })

        # ⭐⭐ 2. Validar rangos (si tenemos todos los datos necesarios)
        if numero_inicial is not None and numero_final is not None:
            if numero_final <= numero_inicial:
                raise serializers.ValidationError({
                    "numero_final": f"Debe ser mayor que el número inicial ({numero_inicial})"
                })

        # ⭐⭐ 3. Validar proximo_numero (si se proporciona)
        if proximo_numero is not None:
            # Si tenemos numero_inicial, validar que no sea menor
            if numero_inicial is not None and proximo_numero < numero_inicial:
                raise serializers.ValidationError({
                    "proximo_numero": f"No puede ser menor que el inicial ({numero_inicial})"
                })
            
            # Si tenemos numero_final, validar que no sea mayor
            if numero_final is not None and proximo_numero > numero_final:
                raise serializers.ValidationError({
                    "proximo_numero": f"No puede ser mayor que el final ({numero_final})"
                })

        # ⭐⭐ 4. Validación especial para actualización
        if self.instance and 'tipo' in data:
            # No permitir cambiar el tipo si ya existe
            if data['tipo'] != self.instance.tipo:
                raise serializers.ValidationError({
                    "tipo": "No se puede cambiar el tipo de una configuración existente"
                })

        if self.instance and 'serie' in data:
            # No permitir cambiar la serie si ya existe
            if data['serie'] != self.instance.serie:
                raise serializers.ValidationError({
                    "serie": "No se puede cambiar la serie de una configuración existente"
                })

        return data

    def create(self, validated_data):
        """
        Crear nueva configuración de numeración
        
        Nota: Por defecto crea con rango 1-999999 y proximo_numero=1
        """
        print(f"📝 Creando configuración: {validated_data.get('tipo')}-{validated_data.get('serie')}")
        
        # Asegurar valores por defecto si no se proporcionan
        if 'numero_inicial' not in validated_data:
            validated_data['numero_inicial'] = 1
        
        if 'numero_final' not in validated_data:
            validated_data['numero_final'] = 999999
        
        if 'proximo_numero' not in validated_data:
            validated_data['proximo_numero'] = validated_data['numero_inicial']
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Actualizar configuración existente
        
        Importante: 
        - No validar contra max(numero) de presupuestos
        - Confiar en que el admin sabe lo que hace al modificar proximo_numero
        """
        print(f"🔄 Actualizando configuración {instance.tipo}-{instance.serie}")
        print(f"   Valores actuales: proximo_numero={instance.proximo_numero}")
        print(f"   Nuevos valores: {validated_data}")
        
        # Si se está modificando proximo_numero, registrar el cambio
        if 'proximo_numero' in validated_data:
            nuevo_proximo = validated_data['proximo_numero']
            if nuevo_proximo != instance.proximo_numero:
                print(f"   ⚠️ Cambio de proximo_numero: {instance.proximo_numero} → {nuevo_proximo}")
        
        return super().update(instance, validated_data)