# gestion/backend/presupuestos/serializers.py

import os
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from .models import Presupuesto, PresupuestoItem, PresupuestoAdjunto
from clientes.models import Cliente
from productos.models import Producto, Servicio
from comprobantes.models import Comprobante


class PresupuestoItemSerializer(serializers.ModelSerializer):
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(),
        allow_null=True,
        required=False,
    )
    servicio = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(),
        allow_null=True,
        required=False,
    )
    codigo = serializers.CharField(max_length=50, allow_blank=True, required=False)
    descripcion = serializers.CharField(max_length=255, allow_blank=True, required=False)
    precio_unitario = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
    )

    class Meta:
        model = PresupuestoItem
        fields = [
            "id",
            "producto",
            "servicio",
            "codigo",
            "descripcion",
            "cantidad",
            "precio_unitario",
        ]

    def validate(self, data):
        if not data.get("producto") and not data.get("servicio"):
            raise serializers.ValidationError(
                "Debe especificar un producto o un servicio."
            )

        if data.get("producto") and data.get("servicio"):
            raise serializers.ValidationError(
                "No puede especificar producto y servicio simultáneamente."
            )

        return data


class PresupuestoSerializer(serializers.ModelSerializer):
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    items = PresupuestoItemSerializer(many=True)
    comprobante = serializers.PrimaryKeyRelatedField(
        queryset=Comprobante.objects.all(),
        allow_null=True,
        required=False,
    )

    numero = serializers.IntegerField(read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    iva_valor = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    anulado_por_nombre = serializers.CharField(
        source="anulado_por.get_full_name",
        read_only=True,
    )
    fecha_anulacion = serializers.DateTimeField(read_only=True)
    motivo_anulacion = serializers.CharField(read_only=True)

    cliente_nombre = serializers.SerializerMethodField()

    def get_cliente_nombre(self, obj):
        if obj.cliente:
            nombre = getattr(obj.cliente, "nombre", "")
            apellido = getattr(obj.cliente, "apellido", "")
            return f"{nombre} {apellido}".strip()
        return ""

    class Meta:
        model = Presupuesto
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "fecha",
            "comprobante",
            "numero",
            "creado_por",
            "valido_hasta",
            "observaciones",
            "condiciones_comerciales",
            "iva_porcentaje",
            "estado",
            "items",
            "subtotal",
            "iva_valor",
            "total",
            "creado",
            "actualizado",
            "anulado_por",
            "anulado_por_nombre",
            "fecha_anulacion",
            "motivo_anulacion",
        ]
        read_only_fields = [
            "creado",
            "actualizado",
            "fecha",
            "total",
            "subtotal",
            "iva_valor",
            "numero",
            "creado_por",
            "anulado_por",
            "fecha_anulacion",
        ]

    def validate(self, data):
        request = self.context.get("request")
        items_data = []

        if request:
            items_data = request.data.get("items", [])

        if not items_data:
            raise serializers.ValidationError(
                "Un presupuesto debe tener al menos un ítem."
            )

        return data

    def _decimal(self, value, default="0.00"):
        if value in (None, "", []):
            return Decimal(default)

        return Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def _precio_item(self, item_data, producto=None, servicio=None):
        """
        Devuelve el precio unitario correcto.

        Prioridad:
        1. precio_unitario enviado desde frontend.
        2. precio_venta del producto.
        3. precio_base del servicio.
        """

        precio_enviado = item_data.get("precio_unitario")

        if precio_enviado not in (None, "", []):
            return self._decimal(precio_enviado)

        if producto:
            return self._decimal(producto.precio_venta)

        if servicio:
            return self._decimal(servicio.precio_base)

        return Decimal("0.00")

    def _normalizar_item(self, item_data):
        """
        Normaliza producto/servicio, código, descripción y precio.

        Importante:
        - No agrupa productos repetidos.
        - Respeta cada fila como la cargó el usuario.
        - Permite mismo producto con distintos precios.
        """

        producto = item_data.get("producto")
        servicio = item_data.get("servicio")

        if producto:
            if isinstance(producto, int):
                producto = Producto.objects.get(pk=producto)

            item_data["producto"] = producto
            item_data["servicio"] = None
            item_data["codigo"] = item_data.get("codigo") or producto.sku or ""
            item_data["descripcion"] = (
                item_data.get("descripcion") or producto.nombre
            )
            item_data["precio_unitario"] = self._precio_item(
                item_data,
                producto=producto,
            )

        elif servicio:
            if isinstance(servicio, int):
                servicio = Servicio.objects.get(pk=servicio)

            item_data["producto"] = None
            item_data["servicio"] = servicio
            item_data["codigo"] = (
                item_data.get("codigo") or servicio.codigo_interno or ""
            )
            item_data["descripcion"] = (
                item_data.get("descripcion") or servicio.nombre
            )
            item_data["precio_unitario"] = self._precio_item(
                item_data,
                servicio=servicio,
            )

        else:
            raise serializers.ValidationError(
                "Cada ítem debe tener un producto o un servicio."
            )

        cantidad = item_data.get("cantidad", 1)

        if cantidad in (None, "", []):
            cantidad = 1

        cantidad = Decimal(str(cantidad))

        if cantidad <= 0:
            raise serializers.ValidationError(
                "La cantidad debe ser mayor a cero."
            )

        item_data["cantidad"] = int(cantidad)

        return item_data

    def _crear_items(self, presupuesto, items_data):
        subtotal = Decimal("0.00")

        for raw_item in items_data:
            item_data = dict(raw_item)
            item_data.pop("id", None)

            item_data = self._normalizar_item(item_data)

            cantidad = Decimal(str(item_data["cantidad"]))
            precio_unitario = item_data["precio_unitario"]

            subtotal += (cantidad * precio_unitario).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            PresupuestoItem.objects.create(
                presupuesto=presupuesto,
                **item_data,
            )

        return subtotal.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def _recalcular_totales(self, presupuesto):
        subtotal = sum(
            (
                item.cantidad * item.precio_unitario
                for item in presupuesto.items.all()
            ),
            Decimal("0.00"),
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        iva_valor = (
            subtotal * Decimal(str(presupuesto.iva_porcentaje)) / Decimal("100.00")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        total = (subtotal + iva_valor).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        presupuesto.subtotal = subtotal
        presupuesto.iva_valor = iva_valor
        presupuesto.total = total
        presupuesto.save(
            update_fields=[
                "subtotal",
                "iva_valor",
                "total",
                "actualizado",
            ]
        )

        return presupuesto

    @transaction.atomic
    def create(self, validated_data):
        comprobante = Comprobante.objects.filter(tipo="PRES").first()

        if not comprobante:
            raise serializers.ValidationError(
                "No hay comprobante de tipo PRES configurado."
            )

        try:
            numero_asignado = comprobante.obtener_siguiente_numero()
        except Exception as e:
            raise serializers.ValidationError(
                f"Error al obtener número: {str(e)}"
            )

        validated_data["comprobante"] = comprobante
        validated_data["numero"] = numero_asignado

        items_data = validated_data.pop("items", [])

        presupuesto = Presupuesto.objects.create(**validated_data)

        self._crear_items(presupuesto, items_data)
        self._recalcular_totales(presupuesto)

        return presupuesto

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", [])

        instance = super().update(instance, validated_data)

        existing_ids = []

        for raw_item in items_data:
            item_data = dict(raw_item)
            item_id = item_data.pop("id", None)

            item_data = self._normalizar_item(item_data)

            if item_id:
                try:
                    item = PresupuestoItem.objects.get(
                        id=item_id,
                        presupuesto=instance,
                    )

                    for attr, value in item_data.items():
                        setattr(item, attr, value)

                    item.save()
                    existing_ids.append(item.id)

                except PresupuestoItem.DoesNotExist:
                    new_item = PresupuestoItem.objects.create(
                        presupuesto=instance,
                        **item_data,
                    )
                    existing_ids.append(new_item.id)

            else:
                new_item = PresupuestoItem.objects.create(
                    presupuesto=instance,
                    **item_data,
                )
                existing_ids.append(new_item.id)

        instance.items.exclude(id__in=existing_ids).delete()

        self._recalcular_totales(instance)

        return instance


class PresupuestoAdjuntoSerializer(serializers.ModelSerializer):
    nombre_archivo = serializers.SerializerMethodField()
    tamaño_formateado = serializers.SerializerMethodField()
    url_descarga = serializers.SerializerMethodField()
    puede_visualizar = serializers.SerializerMethodField()
    subido_por_nombre = serializers.CharField(
        source="subido_por.get_full_name",
        read_only=True,
    )
    presupuesto_display = serializers.CharField(
        source="presupuesto.__str__",
        read_only=True,
    )

    class Meta:
        model = PresupuestoAdjunto
        fields = [
            "id",
            "presupuesto",
            "presupuesto_display",
            "archivo",
            "tipo",
            "nombre_original",
            "nombre_archivo",
            "descripcion",
            "tamaño",
            "tamaño_formateado",
            "extension",
            "subido_por",
            "subido_por_nombre",
            "fecha_subida",
            "fecha_modificacion",
            "url_descarga",
            "puede_visualizar",
            "es_publico",
            "version",
            "checksum",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "subido_por",
            "fecha_subida",
            "fecha_modificacion",
            "tamaño",
            "extension",
            "nombre_original",
            "checksum",
            "version",
        ]

    def get_nombre_archivo(self, obj):
        return os.path.basename(obj.archivo.name) if obj.archivo else ""

    def get_tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()

    def get_url_descarga(self, obj):
        return obj.url_descarga

    def get_puede_visualizar(self, obj):
        return obj.puede_visualizar

    def validate_archivo(self, archivo):
        if archivo:
            if archivo.size > settings.MAX_TAMAÑO_ADJUNTO:
                raise serializers.ValidationError(
                    f"El archivo es demasiado grande. "
                    f"Tamaño máximo: {settings.MAX_TAMAÑO_ADJUNTO / (1024 * 1024)} MB"
                )

        return archivo

    def create(self, validated_data):
        validated_data["subido_por"] = self.context["request"].user
        return super().create(validated_data)