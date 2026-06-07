# gestion/backend/pedidos_internos/api/serializers.py

from rest_framework import serializers

from productos.models import Producto, Servicio

from ..models import (
    Sector,
    UsuarioSector,
    PedidoInterno,
    PedidoInternoDetalle,
    PedidoDestino,
    PedidoMovimiento,
)
from ..services import pedido_service


# ==========================================================
# SECTOR / USUARIO-SECTOR
# ==========================================================

class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = [
            "id",
            "codigo",
            "nombre",
            "descripcion",
            "direccion",
            "ciudad",
            "provincia",
            "activo",
            "creado",
            "actualizado",
        ]
        read_only_fields = ["id", "creado", "actualizado"]


class UsuarioSectorSerializer(serializers.ModelSerializer):
    sector_codigo = serializers.CharField(source="sector.codigo", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = UsuarioSector
        fields = [
            "id",
            "usuario",
            "usuario_username",
            "sector",
            "sector_codigo",
            "principal",
            "activo",
        ]
        read_only_fields = ["id"]


# ==========================================================
# RENGLONES / DESTINOS / MOVIMIENTOS
# ==========================================================

class PedidoInternoDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoInternoDetalle
        fields = [
            "id",
            "producto",
            "servicio",
            "descripcion",
            "cantidad",
            "observacion",
        ]
        read_only_fields = ["id"]


class PedidoDestinoSerializer(serializers.ModelSerializer):
    sector_codigo = serializers.CharField(source="sector_destino.codigo", read_only=True)
    sector_nombre = serializers.CharField(source="sector_destino.nombre", read_only=True)

    class Meta:
        model = PedidoDestino
        fields = [
            "id",
            "sector_destino",
            "sector_codigo",
            "sector_nombre",
            "estado",
            "leido",
            "fecha_leido",
            "responsable",
            "observacion",
        ]
        read_only_fields = ["id", "leido", "fecha_leido"]


class PedidoMovimientoSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = PedidoMovimiento
        fields = [
            "id",
            "usuario",
            "usuario_username",
            "accion",
            "detalle",
            "fecha",
        ]
        read_only_fields = fields


# ==========================================================
# PEDIDO INTERNO: LECTURA
# ==========================================================

class PedidoInternoListSerializer(serializers.ModelSerializer):
    solicitante_username = serializers.CharField(source="solicitante.username", read_only=True)
    sector_origen_codigo = serializers.CharField(source="sector_origen.codigo", read_only=True)

    class Meta:
        model = PedidoInterno
        fields = [
            "id",
            "numero",
            "fecha",
            "solicitante",
            "solicitante_username",
            "sector_origen",
            "sector_origen_codigo",
            "estado",
            "prioridad",
            "creado",
            "actualizado",
        ]
        read_only_fields = fields


class PedidoInternoDetalleReadSerializer(serializers.ModelSerializer):
    solicitante_username = serializers.CharField(source="solicitante.username", read_only=True)
    sector_origen_codigo = serializers.CharField(source="sector_origen.codigo", read_only=True)
    detalles = PedidoInternoDetalleSerializer(many=True, read_only=True)
    destinos = PedidoDestinoSerializer(many=True, read_only=True)
    movimientos = PedidoMovimientoSerializer(many=True, read_only=True)

    class Meta:
        model = PedidoInterno
        fields = [
            "id",
            "numero",
            "fecha",
            "solicitante",
            "solicitante_username",
            "sector_origen",
            "sector_origen_codigo",
            "estado",
            "prioridad",
            "observaciones",
            "creado",
            "actualizado",
            "detalles",
            "destinos",
            "movimientos",
        ]
        read_only_fields = fields


# ==========================================================
# PEDIDO INTERNO: CREACIÓN (write anidado)
# ==========================================================

class DetalleInputSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(), required=False, allow_null=True,
    )
    servicio = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(), required=False, allow_null=True,
    )
    descripcion = serializers.CharField(required=False, allow_blank=True, default="")
    cantidad = serializers.IntegerField(min_value=1, default=1)
    observacion = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        if data.get("producto") and data.get("servicio"):
            raise serializers.ValidationError(
                "Un renglón no puede tener producto y servicio a la vez."
            )
        if not data.get("producto") and not data.get("servicio") \
                and not (data.get("descripcion") or "").strip():
            raise serializers.ValidationError(
                "Cada renglón necesita producto, servicio o descripción."
            )
        return data


class PedidoInternoCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleInputSerializer(many=True, write_only=True)
    destinos = serializers.PrimaryKeyRelatedField(
        queryset=Sector.objects.filter(activo=True),
        many=True,
        write_only=True,
    )

    class Meta:
        model = PedidoInterno
        fields = [
            "id",
            "fecha",
            "sector_origen",
            "prioridad",
            "observaciones",
            "detalles",
            "destinos",
        ]
        read_only_fields = ["id"]

    def validate_detalles(self, value):
        if not value:
            raise serializers.ValidationError("El pedido debe tener al menos un renglón.")
        return value

    def validate_destinos(self, value):
        if not value:
            raise serializers.ValidationError("El pedido debe tener al menos un destino.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        detalles = validated_data.pop("detalles")
        destinos = validated_data.pop("destinos")

        return pedido_service.crear_pedido(
            solicitante=request.user,
            sector_origen=validated_data["sector_origen"],
            detalles=detalles,
            destinos=destinos,
            prioridad=validated_data.get("prioridad", "normal"),
            observaciones=validated_data.get("observaciones", ""),
            fecha=validated_data.get("fecha"),
        )

    def to_representation(self, instance):
        return PedidoInternoDetalleReadSerializer(instance, context=self.context).data
