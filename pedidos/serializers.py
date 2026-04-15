# gestion_servicios/pedidos/serializers.py
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from productos.models import Producto, Servicio

from .models import Pedido, PedidoItem


class PedidoItemCreateSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(),
        required=False,
        allow_null=True
    )
    servicio = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(),
        required=False,
        allow_null=True
    )
    cantidad = serializers.IntegerField(min_value=1)

    def validate(self, data):
        producto = data.get("producto")
        servicio = data.get("servicio")

        if producto and servicio:
            raise serializers.ValidationError(
                "Un ítem no puede tener producto y servicio al mismo tiempo."
            )

        if not producto and not servicio:
            raise serializers.ValidationError(
                "Debe enviar un producto o un servicio."
            )

        return data


class PedidoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoItem
        fields = [
            "id",
            "tipo_item",
            "producto",
            "servicio",
            "nombre_snapshot",
            "codigo_snapshot",
            "precio_unitario_snapshot",
            "cantidad",
            "subtotal",
        ]
        read_only_fields = [
            "id",
            "tipo_item",
            "nombre_snapshot",
            "codigo_snapshot",
            "precio_unitario_snapshot",
            "subtotal",
        ]


class PedidoSerializer(serializers.ModelSerializer):
    items = PedidoItemCreateSerializer(many=True)

    class Meta:
        model = Pedido
        fields = [
            "id",
            "estado",
            "observaciones_cliente",
            "observaciones_internas",
            "subtotal",
            "total",
            "activo",
            "creado",
            "actualizado",
            "items",
        ]
        read_only_fields = [
            "id",
            "estado",
            "observaciones_internas",
            "subtotal",
            "total",
            "activo",
            "creado",
            "actualizado",
        ]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("El pedido debe tener al menos un ítem.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        items_data = validated_data.pop("items", [])

        user = request.user
        if not user.is_authenticated:
            raise serializers.ValidationError("Debes estar autenticado para crear pedidos.")

        if not hasattr(user, "cliente_web"):
            raise serializers.ValidationError("El usuario autenticado no tiene perfil web.")

        cliente_web = user.cliente_web
        cliente = cliente_web.cliente if cliente_web.cliente else None

        pedido = Pedido.objects.create(
            cliente_web=cliente_web,
            cliente=cliente,
            **validated_data
        )

        for item_data in items_data:
            producto = item_data.get("producto")
            servicio = item_data.get("servicio")
            cantidad = item_data.get("cantidad", 1)

            if producto:
                PedidoItem.objects.create(
                    pedido=pedido,
                    tipo_item="mercaderia",
                    producto=producto,
                    servicio=None,
                    nombre_snapshot=producto.nombre,
                    codigo_snapshot=producto.sku or "",
                    precio_unitario_snapshot=Decimal(producto.precio_venta or "0.00"),
                    cantidad=cantidad,
                )

            elif servicio:
                PedidoItem.objects.create(
                    pedido=pedido,
                    tipo_item="servicio",
                    producto=None,
                    servicio=servicio,
                    nombre_snapshot=servicio.nombre,
                    codigo_snapshot=servicio.codigo_interno or "",
                    precio_unitario_snapshot=Decimal(servicio.precio_base or "0.00"),
                    cantidad=cantidad,
                )

        pedido.refresh_from_db()
        return pedido


class PedidoDetalleSerializer(serializers.ModelSerializer):
    items = PedidoItemSerializer(many=True, read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    cliente_web_email = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "cliente_web",
            "cliente_web_email",
            "cliente",
            "cliente_nombre",
            "estado",
            "observaciones_cliente",
            "observaciones_internas",
            "subtotal",
            "total",
            "activo",
            "creado",
            "actualizado",
            "items",
        ]

    def get_cliente_nombre(self, obj):
        if not obj.cliente:
            return ""
        nombre = obj.cliente.nombre or ""
        apellido = obj.cliente.apellido or ""
        return f"{nombre} {apellido}".strip()

    def get_cliente_web_email(self, obj):
        if not obj.cliente_web:
            return ""
        return obj.cliente_web.user.email