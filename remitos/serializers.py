# backend/remitos/serializers.py

from rest_framework import serializers
from .models import Remito, ItemRemito, RemitoAdjunto
from comprobantes.models import Comprobante


class ItemRemitoSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = ItemRemito
        fields = [
            'id',
            'codigo',
            'descripcion',
            'cantidad',
            'unidad_medida',
            'observaciones',
            'orden',
            'subtotal'
        ]

        extra_kwargs = {
            'orden': {'required': False, 'default': 0}
        }

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La cantidad debe ser mayor a cero"
            )
        return value

    def validate(self, data):
        if not data.get('descripcion'):
            raise serializers.ValidationError({
                'descripcion': 'La descripción es obligatoria'
            })

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
    creado_por_info = serializers.SerializerMethodField()

    total_items = serializers.IntegerField(
        read_only=True,
        source='items.count'
    )

    comprobante = serializers.PrimaryKeyRelatedField(
        queryset=Comprobante.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Remito

        fields = [
            'id',
            'comprobante',
            'comprobante_info',
            'numero',
            'numero_formateado',

            'cliente',
            'cliente_info',

            'fecha_emision',
            'fecha_entrega',

            'origen',
            'destino',

            'presupuesto_relacionado',
            'licitacion_orden',
            'numero_referencia',

            'observaciones',
            'estado',

            'items',
            'total_items',

            'creado_por',
            'creado_por_info',

            'creado',
            'actualizado',

            'anulado_por',
            'fecha_anulacion',
            'motivo_anulacion',

            'numeros_disponibles_restantes'
        ]

        read_only_fields = [
            'numero',
            'numero_formateado',
            'creado_por',
            'creado',
            'actualizado',
            'anulado_por',
            'fecha_anulacion',
            'total_items',
            'numeros_disponibles_restantes'
        ]

    # =========================================================
    # INFO EXTRA
    # =========================================================

    def get_comprobante_info(self, obj):
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
        if obj.creado_por:
            return {
                'id': obj.creado_por.id,
                'username': obj.creado_por.username,
                'email': obj.creado_por.email,
                'nombre_completo': f"{obj.creado_por.first_name} {obj.creado_por.last_name}".strip()
            }

        return None

    # =========================================================
    # VALIDACIONES
    # =========================================================

    def validate(self, data):
        items_data = data.get('items', [])

        request = self.context.get('request')

        if request and request.method in ['POST', 'PUT', 'PATCH']:
            if not items_data and not self.instance:
                raise serializers.ValidationError({
                    'items': 'Un remito debe tener al menos un ítem.'
                })

        fecha_emision = data.get('fecha_emision')
        fecha_entrega = data.get('fecha_entrega')

        if fecha_emision and fecha_entrega:
            if fecha_entrega < fecha_emision:
                raise serializers.ValidationError({
                    'fecha_entrega': 'La fecha de entrega no puede ser anterior a la fecha de emisión'
                })

        estado = data.get('estado')

        if estado and estado not in dict(Remito.ESTADO_CHOICES):
            raise serializers.ValidationError({
                'estado': 'Estado inválido'
            })

        comprobante = data.get('comprobante')

        if comprobante and comprobante.tipo != 'REMI':
            raise serializers.ValidationError({
                'comprobante': 'El comprobante debe ser de tipo REMI'
            })

        return data

    # =========================================================
    # CREATE
    # =========================================================

    def create(self, validated_data):
        items_data = validated_data.pop('items')

        request = self.context.get('request')

        if request and request.user:
            validated_data['creado_por'] = request.user

        if 'comprobante' not in validated_data:
            comprobante = Comprobante.objects.filter(
                tipo='REMI'
            ).first()

            if not comprobante:
                raise serializers.ValidationError({
                    'comprobante': 'No hay comprobante REMI configurado'
                })

            validated_data['comprobante'] = comprobante

        remito = Remito.objects.create(**validated_data)

        for item_data in items_data:
            ItemRemito.objects.create(
                remito=remito,
                **item_data
            )

        return remito

    # =========================================================
    # UPDATE
    # =========================================================

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        nuevo_estado = validated_data.get('estado', instance.estado)

        # =====================================================
        # REGLAS DE NEGOCIO
        # =====================================================

        if instance.estado == 'anulado':
            raise serializers.ValidationError(
                "No se puede modificar un remito anulado"
            )

        # Si YA está entregado → no permitir modificar
        if instance.estado == 'entregado':

            # No permitir volver atrás
            if nuevo_estado != 'entregado':
                raise serializers.ValidationError(
                    "Un remito entregado no puede volver a otro estado"
                )

            # No permitir editar datos
            campos_editados = [
                k for k in validated_data.keys()
                if k != 'estado'
            ]

            if campos_editados:
                raise serializers.ValidationError(
                    "No se puede editar un remito entregado"
                )

            # No permitir editar items
            if items_data is not None:
                raise serializers.ValidationError(
                    "No se pueden modificar items de un remito entregado"
                )

        # =====================================================
        # ACTUALIZAR CAMPOS
        # =====================================================

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # =====================================================
        # ACTUALIZAR ITEMS
        # =====================================================

        if items_data is not None:

            existing_ids = []

            for item_data in items_data:

                item_id = item_data.get('id')

                if item_id:

                    try:
                        item = ItemRemito.objects.get(
                            id=item_id,
                            remito=instance
                        )

                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(item, attr, value)

                        item.save()

                        existing_ids.append(item.id)

                    except ItemRemito.DoesNotExist:

                        item_data.pop('id', None)

                        new_item = ItemRemito.objects.create(
                            remito=instance,
                            **item_data
                        )

                        existing_ids.append(new_item.id)

                else:

                    new_item = ItemRemito.objects.create(
                        remito=instance,
                        **item_data
                    )

                    existing_ids.append(new_item.id)

            instance.items.exclude(
                id__in=existing_ids
            ).delete()

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
            'id',
            'remito',
            'archivo',
            'tipo',
            'nombre_original',
            'nombre_archivo',
            'descripcion',
            'tamaño',
            'tamaño_formateado',
            'extension',
            'url_descarga',
            'puede_visualizar',
            'subido_por',
            'subido_por_info',
            'fecha_subida',
            'fecha_modificacion'
        ]

        read_only_fields = [
            'remito',
            'tamaño',
            'extension',
            'nombre_original',
            'subido_por',
            'fecha_subida',
            'fecha_modificacion',
            'nombre_archivo',
            'tamaño_formateado',
            'url_descarga',
            'puede_visualizar',
            'subido_por_info'
        ]

    def get_nombre_archivo(self, obj):
        import os
        return os.path.basename(obj.archivo.name) if obj.archivo else ''

    def get_tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()

    def get_url_descarga(self, obj):
        if obj.archivo:
            request = self.context.get('request')

            if request:
                return request.build_absolute_uri(obj.archivo.url)

            return obj.archivo.url

        return ''

    def get_puede_visualizar(self, obj):
        extensiones_visualizables = [
            'pdf',
            'jpg',
            'jpeg',
            'png',
            'gif',
            'bmp',
            'webp'
        ]

        return obj.extension.lower() in extensiones_visualizables

    def get_subido_por_info(self, obj):
        if obj.subido_por:
            return {
                'id': obj.subido_por.id,
                'username': obj.subido_por.username,
                'nombre_completo': f"{obj.subido_por.first_name} {obj.subido_por.last_name}".strip()
            }

        return None

    def validate(self, data):
        archivo = data.get('archivo')

        if archivo:

            tamaño_maximo = 10 * 1024 * 1024

            if archivo.size > tamaño_maximo:
                raise serializers.ValidationError({
                    'archivo': 'Archivo demasiado grande'
                })

            extensiones_permitidas = [
                'pdf',
                'jpg',
                'jpeg',
                'png',
                'gif',
                'bmp',
                'webp',
                'txt',
                'doc',
                'docx',
                'xls',
                'xlsx'
            ]

            import os

            extension = os.path.splitext(
                archivo.name
            )[1].lower().replace('.', '')

            if extension not in extensiones_permitidas:
                raise serializers.ValidationError({
                    'archivo': 'Extensión no permitida'
                })

        return data

    def create(self, validated_data):
        request = self.context.get('request')

        if request and request.user:
            validated_data['subido_por'] = request.user

        return super().create(validated_data)


class RemitoListSerializer(serializers.ModelSerializer):
    numero_formateado = serializers.CharField(read_only=True)

    cliente_nombre = serializers.CharField(
        source='cliente.nombre',
        read_only=True
    )

    estado_display = serializers.CharField(
        source='get_estado_display',
        read_only=True
    )

    total_items = serializers.IntegerField(
        source='items.count',
        read_only=True
    )

    class Meta:
        model = Remito

        fields = [
            'id',
            'numero',
            'numero_formateado',
            'cliente',
            'cliente_nombre',
            'fecha_emision',
            'estado',
            'estado_display',
            'total_items',
            'presupuesto_relacionado',
            'creado'
        ]


class ItemRemitoListSerializer(serializers.ModelSerializer):
    remito_info = serializers.SerializerMethodField()

    class Meta:
        model = ItemRemito

        fields = [
            'id',
            'remito',
            'remito_info',
            'codigo',
            'descripcion',
            'cantidad',
            'unidad_medida',
            'orden'
        ]

    def get_remito_info(self, obj):
        if obj.remito:
            return {
                'id': obj.remito.id,
                'numero_formateado': obj.remito.numero_formateado,
                'cliente_nombre': obj.remito.cliente.nombre if obj.remito.cliente else '',
                'fecha_emision': obj.remito.fecha_emision
            }

        return None
