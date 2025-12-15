# gestion/remitos/serializers.py
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Remito, ItemRemito, RemitoAdjunto
from comprobantes.models import Comprobante
from clientes.serializers import ClienteSerializer  # Opcional: para detalles del cliente


class ItemRemitoSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = ItemRemito
        fields = [
            'id', 'codigo', 'descripcion', 'cantidad', 
            'unidad_medida', 'observaciones', 'orden', 'subtotal'
        ]
        extra_kwargs = {
            'orden': {'required': False, 'default': 0}
        }
    
    def validate_cantidad(self, value):
        """Validar que la cantidad sea positiva"""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a cero")
        return value
    
    def validate(self, data):
        """Validaciones adicionales"""
        # Validar que haya descripción
        if not data.get('descripcion'):
            raise serializers.ValidationError({
                'descripcion': 'La descripción es obligatoria'
            })
        
        # Validar unidad de medida
        unidad = data.get('unidad_medida', 'UNIDAD').strip()
        if len(unidad) > 20:
            raise serializers.ValidationError({
                'unidad_medida': 'La unidad de medida no puede exceder 20 caracteres'
            })
        
        return data


class RemitoSerializer(serializers.ModelSerializer):
    items = ItemRemitoSerializer(many=True)
    numero_formateado = serializers.CharField(read_only=True)
    comprobante_info = serializers.SerializerMethodField()
    cliente_info = serializers.SerializerMethodField()
    total_items = serializers.IntegerField(read_only=True, source='items.count')
    creado_por_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Remito
        fields = [
            'id', 'comprobante', 'comprobante_info', 'numero', 'numero_formateado',
            'cliente', 'cliente_info', 'fecha_emision', 'fecha_entrega',
            'origen', 'destino',
            'presupuesto_relacionado', 'licitacion_orden', 'numero_referencia',
            'observaciones', 'estado', 'items', 'total_items',
            'creado_por', 'creado_por_info', 'creado', 'actualizado',
            'anulado_por', 'fecha_anulacion', 'motivo_anulacion',
            'numeros_disponibles_restantes'  # Propiedad del modelo
        ]
        read_only_fields = [
            'numero', 'numero_formateado', 'creado_por', 'creado', 
            'actualizado', 'anulado_por', 'fecha_anulacion', 'total_items',
            'numeros_disponibles_restantes'
        ]
    
    def get_comprobante_info(self, obj):
        """Información del comprobante"""
        if obj.comprobante:
            return {
                'id': obj.comprobante.id,
                'serie': obj.comprobante.serie,
                'tipo': obj.comprobante.get_tipo_display(),
                'numeros_disponibles': obj.comprobante.numeros_disponibles,
                'porcentaje_usado': obj.comprobante.porcentaje_usado
            }
        return None
    
    def get_cliente_info(self, obj):
        """Información básica del cliente"""
        if obj.cliente:
            return {
                'id': obj.cliente.id,
                'nombre': f"{obj.cliente.nombre} {getattr(obj.cliente, 'apellido', '')}".strip(),
                'documento': getattr(obj.cliente, 'documento', ''),
                'direccion': getattr(obj.cliente, 'direccion', ''),
                'email': getattr(obj.cliente, 'email', '')
            }
        return None
    
    def get_creado_por_info(self, obj):
        """Información del usuario creador"""
        if obj.creado_por:
            return {
                'id': obj.creado_por.id,
                'username': obj.creado_por.username,
                'email': obj.creado_por.email,
                'nombre_completo': f"{obj.creado_por.first_name} {obj.creado_por.last_name}".strip()
            }
        return None
    
    def validate(self, data):
        """Validaciones generales del remito"""
        
        # Validar que haya items
        items_data = data.get('items', [])
        request = self.context.get('request')
        
        if request and request.method in ['POST', 'PUT', 'PATCH']:
            if not items_data and not self.instance:
                raise serializers.ValidationError({
                    'items': 'Un remito debe tener al menos un ítem.'
                })
        
        # Validar fechas
        fecha_emision = data.get('fecha_emision')
        fecha_entrega = data.get('fecha_entrega')
        
        if fecha_emision and fecha_entrega:
            if fecha_entrega < fecha_emision:
                raise serializers.ValidationError({
                    'fecha_entrega': 'La fecha de entrega no puede ser anterior a la fecha de emisión'
                })
        
        # Validar estado
        estado = data.get('estado')
        if estado and estado not in dict(Remito.ESTADO_CHOICES):
            raise serializers.ValidationError({
                'estado': f'Estado inválido. Opciones: {list(dict(Remito.ESTADO_CHOICES).keys())}'
            })
        
        # Validar comprobante si se proporciona
        comprobante = data.get('comprobante')
        if comprobante and comprobante.tipo != 'REMI':
            raise serializers.ValidationError({
                'comprobante': 'El comprobante debe ser de tipo REMI (Remito Interno)'
            })
        
        return data
    
    def create(self, validated_data):
        """Crear remito con items"""
        items_data = validated_data.pop('items')
        
        # Asignar usuario creador
        request = self.context.get('request')
        if request and request.user:
            validated_data['creado_por'] = request.user
        
        # Crear remito
        remito = Remito.objects.create(**validated_data)
        
        # Crear items
        for item_data in items_data:
            ItemRemito.objects.create(remito=remito, **item_data)
        
        return remito
    
    def update(self, instance, validated_data):
        """Actualizar remito y sus items"""
        items_data = validated_data.pop('items', None)
        
        # Validar que no se pueda modificar remitos anulados
        if instance.estado == 'anulado':
            raise ValidationError("No se puede modificar un remito anulado")
        
        # Actualizar campos del remito
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Actualizar items si se enviaron
        if items_data is not None:
            # Validar que no se modifiquen items de remitos entregados
            if instance.estado == 'entregado':
                raise ValidationError("No se pueden modificar items de un remito entregado")
            
            existing_ids = []
            
            for item_data in items_data:
                item_id = item_data.get('id')
                
                if item_id:
                    try:
                        item = ItemRemito.objects.get(id=item_id, remito=instance)
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(item, attr, value)
                        item.save()
                        existing_ids.append(item_id)
                    except ItemRemito.DoesNotExist:
                        # Si el ID no existe, crear nuevo item
                        item_data.pop('id', None)
                        new_item = ItemRemito.objects.create(remito=instance, **item_data)
                        existing_ids.append(new_item.id)
                else:
                    # Crear nuevo item sin ID
                    new_item = ItemRemito.objects.create(remito=instance, **item_data)
                    existing_ids.append(new_item.id)
            
            # Eliminar items no incluidos
            instance.items.exclude(id__in=existing_ids).delete()
        
        return instance


class RemitoAdjuntoSerializer(serializers.ModelSerializer):
    nombre_archivo = serializers.SerializerMethodField()
    tamaño_formateado = serializers.SerializerMethodField()
    url_descarga = serializers.SerializerMethodField()
    puede_visualizar = serializers.SerializerMethodField()
    subido_por_info = serializers.SerializerMethodField()
    
    class Meta:
        model = RemitoAdjunto
        fields = [
            'id', 'remito', 'archivo', 'tipo', 'nombre_original', 'nombre_archivo',
            'descripcion', 'tamaño', 'tamaño_formateado', 'extension',
            'url_descarga', 'puede_visualizar',
            'subido_por', 'subido_por_info', 'fecha_subida', 'fecha_modificacion'
        ]
        read_only_fields = [
            'tamaño', 'extension', 'nombre_original', 'subido_por',
            'fecha_subida', 'fecha_modificacion', 'nombre_archivo',
            'tamaño_formateado', 'url_descarga', 'puede_visualizar', 'subido_por_info'
        ]
    
    def get_nombre_archivo(self, obj):
        import os
        return os.path.basename(obj.archivo.name) if obj.archivo else ''
    
    def get_tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()
    
    def get_url_descarga(self, obj):
        """URL para descargar el archivo"""
        if obj.archivo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.archivo.url)
            return obj.archivo.url
        return ''
    
    def get_puede_visualizar(self, obj):
        """Determina si el archivo puede ser visualizado en el navegador"""
        extensiones_visualizables = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        return obj.extension.lower() in extensiones_visualizables
    
    def get_subido_por_info(self, obj):
        """Información del usuario que subió el archivo"""
        if obj.subido_por:
            return {
                'id': obj.subido_por.id,
                'username': obj.subido_por.username,
                'nombre_completo': f"{obj.subido_por.first_name} {obj.subido_por.last_name}".strip()
            }
        return None
    
    def validate(self, data):
        """Validaciones del adjunto"""
        archivo = data.get('archivo')
        
        if archivo:
            # Validar tamaño máximo (10MB)
            tamaño_maximo = 10 * 1024 * 1024  # 10MB
            if archivo.size > tamaño_maximo:
                raise serializers.ValidationError({
                    'archivo': f'El archivo es demasiado grande. Tamaño máximo: {tamaño_maximo/(1024*1024)}MB'
                })
            
            # Validar extensiones permitidas
            extensiones_permitidas = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'txt', 'doc', 'docx', 'xls', 'xlsx']
            import os
            extension = os.path.splitext(archivo.name)[1].lower().replace('.', '')
            
            if extension not in extensiones_permitidas:
                raise serializers.ValidationError({
                    'archivo': f'Extensión no permitida. Extensiones válidas: {", ".join(extensiones_permitidas)}'
                })
        
        return data
    
    def create(self, validated_data):
        """Crear adjunto asignando usuario"""
        request = self.context.get('request')
        if request and request.user:
            validated_data['subido_por'] = request.user
        
        return super().create(validated_data)


# Serializers para listados y búsquedas
class RemitoListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    numero_formateado = serializers.CharField(read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    total_items = serializers.IntegerField(source='items.count', read_only=True)
    
    class Meta:
        model = Remito
        fields = [
            'id', 'numero', 'numero_formateado', 'cliente', 'cliente_nombre',
            'fecha_emision', 'estado', 'estado_display', 'total_items',
            'presupuesto_relacionado', 'creado'
        ]


class ItemRemitoListSerializer(serializers.ModelSerializer):
    """Serializer para listado de items"""
    remito_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ItemRemito
        fields = [
            'id', 'remito', 'remito_info', 'codigo', 'descripcion',
            'cantidad', 'unidad_medida', 'orden'
        ]
    
    def get_remito_info(self, obj):
        """Información básica del remito"""
        if obj.remito:
            return {
                'id': obj.remito.id,
                'numero_formateado': obj.remito.numero_formateado,
                'cliente_nombre': obj.remito.cliente.nombre if obj.remito.cliente else '',
                'fecha_emision': obj.remito.fecha_emision
            }
        return None