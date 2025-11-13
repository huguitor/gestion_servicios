# gestion/presupuestos/serializers.py
import os
from django.conf import settings
from rest_framework import serializers
from .models import Presupuesto, PresupuestoItem, PresupuestoAdjunto
from clientes.models import Cliente
from productos.models import Producto, Servicio
from comprobantes.models import Comprobante
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction

class PresupuestoItemSerializer(serializers.ModelSerializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all(), allow_null=True)
    servicio = serializers.PrimaryKeyRelatedField(queryset=Servicio.objects.all(), allow_null=True)
    codigo = serializers.CharField(max_length=50, allow_blank=True, required=False)
    descripcion = serializers.CharField(max_length=255, allow_blank=True, required=False)
    precio_unitario = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False)

    class Meta:
        model = PresupuestoItem
        fields = ['id', 'producto', 'servicio', 'codigo', 'descripcion', 'cantidad', 'precio_unitario']

    def validate(self, data):
        if not data.get('producto') and not data.get('servicio'):
            raise serializers.ValidationError("Debe especificar un producto o un servicio.")
        if data.get('producto') and data.get('servicio'):
            raise serializers.ValidationError("No puede especificar producto y servicio simultáneamente.")
        return data


class PresupuestoSerializer(serializers.ModelSerializer):
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    items = PresupuestoItemSerializer(many=True)
    comprobante = serializers.PrimaryKeyRelatedField(queryset=Comprobante.objects.all(), allow_null=True, required=False)
    numero = serializers.IntegerField(read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    iva_valor = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    #cliente_display_name = serializers.CharField(source='cliente.__str__', read_only=True)
    #cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    def get_cliente_nombre(self, obj):
        if obj.cliente:
            nombre = getattr(obj.cliente, 'nombre', '')
            apellido = getattr(obj.cliente, 'apellido', '')
            return f"{nombre} {apellido}".strip()
        return ''




    class Meta:
        model = Presupuesto
        fields = [
            'id', 'cliente', 'cliente_nombre', 'fecha', 'comprobante', 'numero', 'creado_por',
            'valido_hasta', 'observaciones', 'condiciones_comerciales', 'iva_porcentaje',
            'estado', 'items', 'subtotal', 'iva_valor', 'total',
            'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado', 'fecha', 'total', 'subtotal', 'iva_valor', 'numero', 'creado_por']

    def validate(self, data):
        items_data = self.context['request'].data.get('items', [])
        if not items_data:
            raise serializers.ValidationError("Un presupuesto debe tener al menos un ítem.")
        return data

    def _crear_actualizar_items(self, presupuesto, items_data):
        subtotal = Decimal('0.00')
        agrupados = {}

        # Agrupar por producto/servicio
        for item in items_data:
            key = (item.get('producto'), item.get('servicio'))
            if key in agrupados:
                agrupados[key]['cantidad'] += item.get('cantidad', 0)
            else:
                agrupados[key] = item.copy()

        for item_data in agrupados.values():
            producto = item_data.get('producto')
            servicio = item_data.get('servicio')

            if producto:
                if isinstance(producto, int):
                    producto = Producto.objects.get(pk=producto)
                item_data['codigo'] = producto.sku or ''
                item_data['descripcion'] = producto.nombre
                precio_unitario = Decimal(producto.precio_venta or '0.00')
                item_data['producto'] = producto
                item_data['servicio'] = None

            elif servicio:
                if isinstance(servicio, int):
                    servicio = Servicio.objects.get(pk=servicio)
                item_data['codigo'] = servicio.codigo_interno or ''
                item_data['descripcion'] = servicio.nombre
                precio_unitario = Decimal(servicio.precio_base or '0.00')
                item_data['producto'] = None
                item_data['servicio'] = servicio
                item_data['precio_unitario'] = precio_unitario

            else:
                precio_unitario = Decimal('0.00')
                item_data['precio_unitario'] = precio_unitario

            cantidad = Decimal(item_data.get('cantidad', 0))
            subtotal += cantidad * precio_unitario

            PresupuestoItem.objects.create(presupuesto=presupuesto, **item_data)

        return subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        presupuesto = Presupuesto.objects.create(**validated_data)
        subtotal = self._crear_actualizar_items(presupuesto, items_data)
        iva_valor = (subtotal * Decimal(presupuesto.iva_porcentaje) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = (subtotal + iva_valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        presupuesto.subtotal = subtotal
        presupuesto.iva_valor = iva_valor
        presupuesto.total = total
        presupuesto.save()
        return presupuesto

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        instance = super().update(instance, validated_data)

        existing_ids = []

        for item_data in items_data:
            item_id = item_data.get('id')

            if item_id:
                try:
                    item = PresupuestoItem.objects.get(id=item_id, presupuesto=instance)
                    for attr, value in item_data.items():
                        if attr != 'id':
                            # Solo actualizar si el valor tiene contenido
                            if value not in ('', None, [], {}):
                                setattr(item, attr, value)
                            # Si es vacío → mantener valor actual
                    item.save()
                    existing_ids.append(item_id)
                except PresupuestoItem.DoesNotExist:
                    item_data.pop('id', None)
                    new_item = PresupuestoItem.objects.create(presupuesto=instance, **item_data)
                    existing_ids.append(new_item.id)
            else:
                new_item = PresupuestoItem.objects.create(presupuesto=instance, **item_data)
                existing_ids.append(new_item.id)

        instance.items.exclude(id__in=existing_ids).delete()

        subtotal = sum(item.cantidad * item.precio_unitario for item in instance.items.all())
        instance.subtotal = subtotal
        instance.iva_valor = subtotal * (instance.iva_porcentaje / 100)
        instance.total = subtotal + instance.iva_valor
        instance.save()

        return instance
    
# presupuestos/serializers.py - AGREGAR al final

class PresupuestoAdjuntoSerializer(serializers.ModelSerializer):
    nombre_archivo = serializers.SerializerMethodField()
    tamaño_formateado = serializers.SerializerMethodField()
    url_descarga = serializers.SerializerMethodField()
    puede_visualizar = serializers.SerializerMethodField()
    subido_por_nombre = serializers.CharField(source='subido_por.get_full_name', read_only=True)
    presupuesto_display = serializers.CharField(source='presupuesto.__str__', read_only=True)

    class Meta:
        model = PresupuestoAdjunto
        fields = [
            'id', 'presupuesto', 'presupuesto_display', 'archivo', 'tipo',
            'nombre_original', 'nombre_archivo', 'descripcion', 'tamaño',
            'tamaño_formateado', 'extension', 'subido_por', 'subido_por_nombre',
            'fecha_subida', 'fecha_modificacion', 'url_descarga', 'puede_visualizar',
            'es_publico', 'version', 'checksum', 'metadata'
        ]
        read_only_fields = [
            'id', 'subido_por', 'fecha_subida', 'fecha_modificacion',
            'tamaño', 'extension', 'nombre_original', 'checksum', 'version'
        ]

    def get_nombre_archivo(self, obj):
        return os.path.basename(obj.archivo.name) if obj.archivo else ''

    def get_tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()

    def get_url_descarga(self, obj):
        return obj.url_descarga

    def get_puede_visualizar(self, obj):
        return obj.puede_visualizar

    def validate_archivo(self, archivo):
        """
        Validación generosa pero segura para archivos
        """
        if archivo:
            # Tamaño máximo
            if archivo.size > settings.MAX_TAMAÑO_ADJUNTO:
                raise serializers.ValidationError(
                    f"El archivo es demasiado grande. Tamaño máximo: {settings.MAX_TAMAÑO_ADJUNTO / (1024*1024)} MB"
                )
        return archivo

    def create(self, validated_data):
        # Asignar usuario automáticamente
        validated_data['subido_por'] = self.context['request'].user
        return super().create(validated_data)