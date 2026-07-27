# gestion/backend/pedidos_internos/api/serializers.py

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from productos.models import Producto, Servicio

from ..models import (
    PedidoDestino,
    PedidoInterno,
    PedidoInternoDetalle,
    PedidoMovimiento,
    Sector,
    UsuarioSector,
)
from ..services import pedido_service
from ..services.sla_service import obtener_sla_actual
from ..services.workflow_permissions import (
    acciones_permitidas,
    puede_cancelar,
)


# ==========================================================
# HELPERS
# ==========================================================

def _nombre_usuario(usuario):
    if usuario is None:
        return None

    nombre_completo = ""

    if hasattr(usuario, "get_full_name"):
        nombre_completo = usuario.get_full_name().strip()

    return nombre_completo or usuario.get_username()


def _serializar_error_django(exc):
    """
    Convierte django.core.exceptions.ValidationError en un formato
    compatible con DRF.
    """
    if hasattr(exc, "message_dict"):
        return exc.message_dict

    if hasattr(exc, "messages"):
        return {"detail": exc.messages}

    return {"detail": [str(exc)]}


# ==========================================================
# USUARIO RESUMIDO
# ==========================================================

class UsuarioResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    nombre = serializers.SerializerMethodField()

    def get_nombre(self, obj):
        return _nombre_usuario(obj)


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
        read_only_fields = [
            "id",
            "creado",
            "actualizado",
        ]


class UsuarioSectorSerializer(serializers.ModelSerializer):
    sector_codigo = serializers.CharField(
        source="sector.codigo",
        read_only=True,
    )

    sector_nombre = serializers.CharField(
        source="sector.nombre",
        read_only=True,
    )

    usuario_username = serializers.CharField(
        source="usuario.username",
        read_only=True,
    )

    class Meta:
        model = UsuarioSector
        fields = [
            "id",
            "usuario",
            "usuario_username",
            "sector",
            "sector_codigo",
            "sector_nombre",
            "principal",
            "activo",
        ]
        read_only_fields = ["id"]


# ==========================================================
# DETALLES
# ==========================================================

class PedidoInternoDetalleSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(
        source="producto.nombre",
        read_only=True,
        default=None,
    )

    servicio_nombre = serializers.CharField(
        source="servicio.nombre",
        read_only=True,
        default=None,
    )

    class Meta:
        model = PedidoInternoDetalle
        fields = [
            "id",
            "tipo",
            "producto",
            "producto_nombre",
            "servicio",
            "servicio_nombre",
            "descripcion",
            "cantidad",
            "observacion",
        ]
        read_only_fields = ["id"]


# ==========================================================
# MOVIMIENTOS
# ==========================================================

class PedidoMovimientoSerializer(serializers.ModelSerializer):
    usuario_detalle = UsuarioResumenSerializer(
        source="usuario",
        read_only=True,
    )

    destino_sector_id = serializers.IntegerField(
        source="destino.sector_destino_id",
        read_only=True,
        allow_null=True,
    )

    destino_sector_codigo = serializers.CharField(
        source="destino.sector_destino.codigo",
        read_only=True,
        allow_null=True,
        default=None,
    )

    accion_display = serializers.CharField(
        source="get_accion_display",
        read_only=True,
    )

    class Meta:
        model = PedidoMovimiento
        fields = [
            "id",
            "pedido",
            "destino",
            "destino_sector_id",
            "destino_sector_codigo",
            "usuario",
            "usuario_detalle",
            "accion",
            "accion_display",
            "estado_anterior",
            "estado_nuevo",
            "detalle",
            "metadata",
            "sla_aplica",
            "sla_limite_horas",
            "sla_duracion_horas",
            "sla_vencido",
            "fecha",
        ]
        read_only_fields = fields


# ==========================================================
# DESTINOS
# ==========================================================

class PedidoDestinoSerializer(serializers.ModelSerializer):
    pedido_fecha = serializers.DateField(
        source="pedido.fecha",
        read_only=True,
    )
    pedido_solicitante = UsuarioResumenSerializer(
        source="pedido.solicitante",
        read_only=True,
    )
    pedido_sector_origen_codigo = serializers.CharField(
        source="pedido.sector_origen.codigo",
        read_only=True,
    )
    pedido_sector_origen_nombre = serializers.CharField(
        source="pedido.sector_origen.nombre",
        read_only=True,
    )
    sector_codigo = serializers.CharField(
        source="sector_destino.codigo",
        read_only=True,
    )

    sector_nombre = serializers.CharField(
        source="sector_destino.nombre",
        read_only=True,
    )

    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
    )

    leido_por_detalle = UsuarioResumenSerializer(
        source="leido_por",
        read_only=True,
    )

    responsable_detalle = UsuarioResumenSerializer(
        source="responsable",
        read_only=True,
    )

    pedido_numero = serializers.IntegerField(
        source="pedido.numero",
        read_only=True,
    )

    pedido_prioridad = serializers.CharField(
        source="pedido.prioridad",
        read_only=True,
    )

    pedido_estado_global = serializers.CharField(
        source="pedido.estado",
        read_only=True,
    )

    sla = serializers.SerializerMethodField()
    acciones_permitidas = serializers.SerializerMethodField()
    ultima_intervencion = serializers.SerializerMethodField()

    class Meta:
        model = PedidoDestino
        fields = [
            "id",
            "pedido",
            "pedido_numero",
            "pedido_fecha",
            "pedido_solicitante",
            "pedido_sector_origen_codigo",
            "pedido_sector_origen_nombre",
            "pedido_prioridad",
            "pedido_estado_global",
            "sector_destino",
            "sector_codigo",
            "sector_nombre",
            "estado",
            "estado_display",
            "fecha_estado",
            "leido",
            "fecha_leido",
            "leido_por",
            "leido_por_detalle",
            "responsable",
            "responsable_detalle",
            "observacion",
            "creado",
            "actualizado",
            "sla",
            "acciones_permitidas",
            "ultima_intervencion",
        ]
        read_only_fields = fields

    def get_sla(self, obj):
        try:
            resultado = obtener_sla_actual(destino=obj)
        except DjangoValidationError:
            return {
                "aplica": False,
                "estado": "error",
            }

        return resultado

    def get_acciones_permitidas(self, obj):
        """
        Informa al frontend qué botones puede mostrar.

        La seguridad real continúa en WorkflowService.
        """
        request = self.context.get("request")

        if request is None:
            return []

        return acciones_permitidas(request.user, obj)

    def get_ultima_intervencion(self, obj):
        movimientos_precargados = getattr(
            obj,
            "_prefetched_objects_cache",
            {},
        ).get("movimientos")

        if movimientos_precargados is not None:
            movimiento = max(
                movimientos_precargados,
                key=lambda item: (item.fecha, item.id),
                default=None,
            )
        else:
            movimiento = (
                obj.movimientos
                .select_related("usuario")
                .order_by("-fecha", "-id")
                .first()
            )

        if movimiento is None:
            return None

        return {
            "id": movimiento.id,
            "accion": movimiento.accion,
            "accion_display": movimiento.get_accion_display(),
            "detalle": movimiento.detalle,
            "fecha": movimiento.fecha,
            "usuario": (
                {
                    "id": movimiento.usuario_id,
                    "username": movimiento.usuario.get_username(),
                    "nombre": _nombre_usuario(movimiento.usuario),
                }
                if movimiento.usuario
                else None
            ),
        }


# ==========================================================
# PEDIDO INTERNO: LISTADO
# ==========================================================

class PedidoInternoListSerializer(serializers.ModelSerializer):
    solicitante_detalle = UsuarioResumenSerializer(
        source="solicitante",
        read_only=True,
    )

    sector_origen_codigo = serializers.CharField(
        source="sector_origen.codigo",
        read_only=True,
    )

    sector_origen_nombre = serializers.CharField(
        source="sector_origen.nombre",
        read_only=True,
    )

    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
    )

    prioridad_display = serializers.CharField(
        source="get_prioridad_display",
        read_only=True,
    )

    cantidad_destinos = serializers.SerializerMethodField()
    cantidad_pendientes = serializers.SerializerMethodField()
    cantidad_resueltos = serializers.SerializerMethodField()
    cantidad_detalles = serializers.SerializerMethodField()
    destinos_resumen = serializers.SerializerMethodField()

    class Meta:
        model = PedidoInterno
        fields = [
            "id",
            "numero",
            "fecha",
            "solicitante",
            "solicitante_detalle",
            "sector_origen",
            "sector_origen_codigo",
            "sector_origen_nombre",
            "estado",
            "estado_display",
            "prioridad",
            "prioridad_display",
            "observaciones",
            "cantidad_destinos",
            "cantidad_pendientes",
            "cantidad_resueltos",
            "cantidad_detalles",
            "destinos_resumen",
            "creado",
            "actualizado",
        ]
        read_only_fields = fields

    def get_cantidad_destinos(self, obj):
        return self._obtener_estados_destino(obj).__len__()

    def get_cantidad_pendientes(self, obj):
        estados = self._obtener_estados_destino(obj)

        return sum(
            estado not in {
                PedidoDestino.Estado.RESUELTO,
                PedidoDestino.Estado.RECHAZADO,
            }
            for estado in estados
        )

    def get_cantidad_resueltos(self, obj):
        estados = self._obtener_estados_destino(obj)

        return sum(
            estado == PedidoDestino.Estado.RESUELTO
            for estado in estados
        )

    def get_cantidad_detalles(self, obj):
        cache = getattr(obj, "_prefetched_objects_cache", {})
        detalles = cache.get("detalles")
        return len(detalles) if detalles is not None else obj.detalles.count()

    def get_destinos_resumen(self, obj):
        cache = getattr(obj, "_prefetched_objects_cache", {})
        destinos = cache.get("destinos")

        if destinos is None:
            destinos = obj.destinos.select_related("sector_destino").all()

        return [
            {
                "id": destino.id,
                "sector_id": destino.sector_destino_id,
                "sector_codigo": destino.sector_destino.codigo,
                "sector_nombre": destino.sector_destino.nombre,
                "estado": destino.estado,
                "estado_display": destino.get_estado_display(),
            }
            for destino in destinos
        ]

    def _obtener_estados_destino(self, obj):
        cache = getattr(
            obj,
            "_prefetched_objects_cache",
            {},
        )

        destinos = cache.get("destinos")

        if destinos is not None:
            return [destino.estado for destino in destinos]

        return list(
            obj.destinos.values_list(
                "estado",
                flat=True,
            )
        )


# ==========================================================
# PEDIDO INTERNO: DETALLE DE LECTURA
# ==========================================================

class PedidoInternoDetalleReadSerializer(serializers.ModelSerializer):
    solicitante_detalle = UsuarioResumenSerializer(
        source="solicitante",
        read_only=True,
    )

    sector_origen_codigo = serializers.CharField(
        source="sector_origen.codigo",
        read_only=True,
    )

    sector_origen_nombre = serializers.CharField(
        source="sector_origen.nombre",
        read_only=True,
    )

    estado_display = serializers.CharField(
        source="get_estado_display",
        read_only=True,
    )

    prioridad_display = serializers.CharField(
        source="get_prioridad_display",
        read_only=True,
    )

    detalles = PedidoInternoDetalleSerializer(
        many=True,
        read_only=True,
    )

    destinos = PedidoDestinoSerializer(
        many=True,
        read_only=True,
    )

    movimientos = PedidoMovimientoSerializer(
        many=True,
        read_only=True,
    )

    puede_cancelar = serializers.SerializerMethodField()

    class Meta:
        model = PedidoInterno
        fields = [
            "id",
            "numero",
            "fecha",
            "solicitante",
            "solicitante_detalle",
            "sector_origen",
            "sector_origen_codigo",
            "sector_origen_nombre",
            "estado",
            "estado_display",
            "prioridad",
            "prioridad_display",
            "observaciones",
            "creado",
            "actualizado",
            "puede_cancelar",
            "detalles",
            "destinos",
            "movimientos",
        ]
        read_only_fields = fields

    def get_puede_cancelar(self, obj):
        request = self.context.get("request")

        if request is None:
            return False

        return puede_cancelar(request.user, obj)


# ==========================================================
# INPUT DE DETALLES
# ==========================================================

class DetalleInputSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(
        choices=PedidoInternoDetalle.TIPO_CHOICES,
    )

    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(),
        required=False,
        allow_null=True,
    )

    servicio = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(),
        required=False,
        allow_null=True,
    )

    descripcion = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    cantidad = serializers.IntegerField(
        min_value=1,
        default=1,
    )

    observacion = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, data):
        tipo = data.get("tipo")
        producto = data.get("producto")
        servicio = data.get("servicio")
        descripcion = (data.get("descripcion") or "").strip()

        if tipo == PedidoInternoDetalle.TIPO_PRODUCTO:
            if producto is None:
                raise serializers.ValidationError({
                    "producto": "Debe seleccionar un producto."
                })

            if servicio is not None:
                raise serializers.ValidationError({
                    "servicio": (
                        "Un detalle de producto no puede "
                        "contener un servicio."
                    )
                })

        elif tipo == PedidoInternoDetalle.TIPO_SERVICIO:
            if servicio is None:
                raise serializers.ValidationError({
                    "servicio": "Debe seleccionar un servicio."
                })

            if producto is not None:
                raise serializers.ValidationError({
                    "producto": (
                        "Un detalle de servicio no puede "
                        "contener un producto."
                    )
                })

        elif tipo == PedidoInternoDetalle.TIPO_OTRO:
            if not descripcion:
                raise serializers.ValidationError({
                    "descripcion": (
                        "Debe indicar una descripción."
                    )
                })

            if producto is not None or servicio is not None:
                raise serializers.ValidationError(
                    "El tipo Otro no admite producto ni servicio."
                )

        else:
            raise serializers.ValidationError(
                "El tipo de detalle es inválido."
            )

        return data


# ==========================================================
# PEDIDO INTERNO: CREACIÓN
# ==========================================================

class PedidoInternoCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleInputSerializer(
        many=True,
        write_only=True,
    )

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
            raise serializers.ValidationError(
                "El pedido debe tener al menos un renglón."
            )

        return value

    def validate_destinos(self, value):
        if not value:
            raise serializers.ValidationError(
                "Debe haber al menos un destino."
            )

        ids = [sector.pk for sector in value]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "No se permiten destinos duplicados."
            )

        return value

    def validate(self, data):
        request = self.context.get("request")

        if request is None:
            raise serializers.ValidationError(
                "No se encontró el contexto de la solicitud."
            )

        usuario = request.user
        sector_origen = data.get("sector_origen")
        destinos = data.get("destinos", [])

        if sector_origen is None:
            raise serializers.ValidationError({
                "sector_origen": (
                    "Debe seleccionar un sector de origen."
                )
            })

        if not sector_origen.activo:
            raise serializers.ValidationError({
                "sector_origen": (
                    "El sector de origen se encuentra inactivo."
                )
            })

        pertenece = UsuarioSector.objects.filter(
            usuario=usuario,
            sector=sector_origen,
            activo=True,
            sector__activo=True,
        ).exists()

        if not pertenece:
            raise serializers.ValidationError({
                "sector_origen": (
                    "El usuario no pertenece activamente "
                    "a este sector."
                )
            })

        if any(
            sector.pk == sector_origen.pk
            for sector in destinos
        ):
            raise serializers.ValidationError({
                "destinos": (
                    "El sector de origen no puede ser también "
                    "un destino inicial."
                )
            })

        return data

    def create(self, validated_data):
        request = self.context["request"]

        detalles = validated_data.pop("detalles")
        destinos = validated_data.pop("destinos")

        try:
            return pedido_service.crear_pedido(
                solicitante=request.user,
                sector_origen=validated_data["sector_origen"],
                detalles=detalles,
                destinos=destinos,
                prioridad=validated_data.get(
                    "prioridad",
                    PedidoInterno.Prioridad.NORMAL,
                ),
                observaciones=validated_data.get(
                    "observaciones",
                    "",
                ),
                fecha=validated_data.get("fecha"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                _serializar_error_django(exc)
            ) from exc

    def to_representation(self, instance):
        return PedidoInternoDetalleReadSerializer(
            instance,
            context=self.context,
        ).data
