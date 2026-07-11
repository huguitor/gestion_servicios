# gestion/backend/pedidos_internos/api/views.py

from django.core.exceptions import ValidationError
from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from licensing.manager import license_manager

from ..models import (
    PedidoDestino,
    PedidoInterno,
    Sector,
)
from ..services import workflow_service
from .serializers import (
    PedidoDestinoSerializer,
    PedidoInternoCreateSerializer,
    PedidoInternoDetalleReadSerializer,
    PedidoInternoListSerializer,
    SectorSerializer,
)


# ==========================================================
# HELPERS GENERALES
# ==========================================================

def _sectores_del_usuario(user):
    """
    IDs de sectores activos a los que pertenece activamente el usuario.
    """
    return list(
        user.sectores
        .filter(
            activo=True,
            sector__activo=True,
        )
        .values_list("sector_id", flat=True)
    )


def _error_validacion(exc):
    """
    Convierte django.core.exceptions.ValidationError en una respuesta
    consistente para DRF.
    """
    if hasattr(exc, "message_dict"):
        return exc.message_dict

    if hasattr(exc, "messages"):
        return {"detail": exc.messages}

    return {"detail": [str(exc)]}


def _serializar_destino(destino, request):
    return PedidoDestinoSerializer(
        destino,
        context={"request": request},
    ).data


def _serializar_pedido(pedido, request):
    return PedidoInternoDetalleReadSerializer(
        pedido,
        context={"request": request},
    ).data


# ==========================================================
# LICENCIA PARA TODAS LAS RUTAS
# ==========================================================

class PedidosInternosLicenseMixin:
    """
    Protege todas las acciones del ViewSet.

    Evita que endpoints personalizados como bandeja, marcar_leido
    o derivar queden accesibles cuando el módulo está deshabilitado.
    """

    modulo_licencia = "pedidos_internos"

    def initial(self, request, *args, **kwargs):
        if not license_manager.is_enabled(self.modulo_licencia):
            raise PermissionDenied(
                "El módulo de pedidos internos no está habilitado."
            )

        return super().initial(request, *args, **kwargs)


# ==========================================================
# SECTORES
# ==========================================================

class SectorViewSet(
    PedidosInternosLicenseMixin,
    viewsets.ModelViewSet,
):
    """
    Lectura para usuarios autenticados.

    Alta, modificación y eliminación únicamente para administradores.
    """

    queryset = Sector.objects.all().order_by("nombre")
    serializer_class = SectorSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]

        return [IsAdminUser()]


# ==========================================================
# PEDIDOS INTERNOS
# ==========================================================

class PedidoInternoViewSet(
    PedidosInternosLicenseMixin,
    viewsets.ModelViewSet,
):
    """
    API principal de pedidos internos.

    La cabecera se puede:

    - listar;
    - consultar;
    - crear.

    No se puede modificar ni eliminar directamente.

    Las operaciones del flujo se ejecutan sobre PedidoDestino
    mediante acciones específicas del WorkflowService.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    # ======================================================
    # QUERYSET Y SERIALIZADORES
    # ======================================================

    def get_queryset(self):
        queryset = (
            PedidoInterno.objects
            .select_related(
                "solicitante",
                "sector_origen",
            )
            .prefetch_related(
                "detalles",
                "destinos",
                "destinos__sector_destino",
                "destinos__responsable",
                "destinos__leido_por",
                "movimientos",
                "movimientos__usuario",
                "movimientos__destino",
            )
        )

        usuario = self.request.user

        if usuario.is_staff or usuario.is_superuser:
            return queryset

        sectores = _sectores_del_usuario(usuario)

        return (
            queryset
            .filter(
                Q(solicitante=usuario)
                | Q(destinos__sector_destino_id__in=sectores)
            )
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return PedidoInternoCreateSerializer

        if self.action in {
            "list",
            "mis_pedidos",
        }:
            return PedidoInternoListSerializer

        return PedidoInternoDetalleReadSerializer

    # ======================================================
    # DESHABILITAR MODIFICACIÓN DIRECTA
    # ======================================================

    def update(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "Los pedidos internos no pueden modificarse "
                    "directamente. Utilice las acciones del workflow."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "Los pedidos internos no pueden modificarse "
                    "directamente. Utilice las acciones del workflow."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "Los pedidos internos no pueden eliminarse. "
                    "Utilice la cancelación lógica."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # ======================================================
    # LISTADOS
    # ======================================================

    @action(
        detail=False,
        methods=["get"],
        url_path="mis-pedidos",
    )
    def mis_pedidos(self, request):
        """
        Pedidos creados por el usuario autenticado.
        """
        queryset = (
            self.get_queryset()
            .filter(solicitante=request.user)
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PedidoInternoListSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = PedidoInternoListSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="bandeja",
    )
    def bandeja(self, request):
        """
        Devuelve los destinos correspondientes a los sectores
        activos del usuario.

        Filtros:

        - ?sector=<id>
        - ?no_leidos=1
        - ?pendientes=1
        - ?estado=pendiente
        - ?responsable=yo
        """

        usuario = request.user

        destinos = (
            PedidoDestino.objects
            .select_related(
                "sector_destino",
                "pedido",
                "pedido__solicitante",
                "pedido__sector_origen",
                "responsable",
                "leido_por",
            )
            .prefetch_related(
                "movimientos",
                "movimientos__usuario",
            )
        )

        if not (usuario.is_staff or usuario.is_superuser):
            sectores = _sectores_del_usuario(usuario)

            destinos = destinos.filter(
                sector_destino_id__in=sectores
            )

        sector_id = request.query_params.get("sector")

        if sector_id:
            destinos = destinos.filter(
                sector_destino_id=sector_id
            )

        if request.query_params.get("no_leidos"):
            destinos = destinos.filter(leido=False)

        if request.query_params.get("pendientes"):
            destinos = destinos.exclude(
                estado__in=[
                    PedidoDestino.Estado.RESUELTO,
                    PedidoDestino.Estado.RECHAZADO,
                ]
            )

        estado_destino = request.query_params.get("estado")

        if estado_destino:
            estados_validos = {
                valor
                for valor, _etiqueta
                in PedidoDestino.Estado.choices
            }

            if estado_destino not in estados_validos:
                return Response(
                    {"detail": "Estado de destino inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            destinos = destinos.filter(
                estado=estado_destino
            )

        if request.query_params.get("responsable") == "yo":
            destinos = destinos.filter(
                responsable=request.user
            )

        destinos = destinos.order_by(
            "-pedido__prioridad",
            "-creado",
        )

        page = self.paginate_queryset(destinos)

        if page is not None:
            serializer = PedidoDestinoSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = PedidoDestinoSerializer(
            destinos,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)

    # ======================================================
    # LECTURA
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="marcar-leido",
    )
    def marcar_leido(self, request, pk=None):
        """
        Registra la primera apertura del destino.

        Body:

        {
            "sector_destino": 3
        }
        """

        pedido = self.get_object()

        destino = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            sector_id=request.data.get("sector_destino"),
        )

        try:
            destino = workflow_service.marcar_leido(
                destino=destino,
                usuario=request.user,
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino.refresh_from_db()

        return Response(
            _serializar_destino(destino, request)
        )

    # ======================================================
    # TOMAR PEDIDO
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="tomar",
    )
    def tomar(self, request, pk=None):
        """
        El sector acepta formalmente gestionar el pedido.

        El usuario autenticado queda como responsable principal.

        Body:

        {
            "sector_destino": 3,
            "detalle": "Opcional"
        }
        """

        pedido = self.get_object()

        destino = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            sector_id=request.data.get("sector_destino"),
        )

        try:
            destino = workflow_service.tomar_pedido(
                destino=destino,
                usuario=request.user,
                detalle=request.data.get("detalle", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino.refresh_from_db()

        return Response(
            _serializar_destino(destino, request)
        )

    # ======================================================
    # INICIAR PROCESO
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="iniciar-proceso",
    )
    def iniciar_proceso(self, request, pk=None):
        """
        Body:

        {
            "sector_destino": 3,
            "detalle": "Opcional"
        }
        """

        pedido = self.get_object()

        destino = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            sector_id=request.data.get("sector_destino"),
        )

        try:
            destino = workflow_service.iniciar_proceso(
                destino=destino,
                usuario=request.user,
                detalle=request.data.get("detalle", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino.refresh_from_db()

        return Response(
            _serializar_destino(destino, request)
        )

    # ======================================================
    # COMENTARIO
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="comentar",
    )
    def comentar(self, request, pk=None):
        """
        Body:

        {
            "sector_destino": 3,
            "comentario": "Texto del comentario"
        }
        """

        pedido = self.get_object()

        destino = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            sector_id=request.data.get("sector_destino"),
        )

        try:
            destino = workflow_service.agregar_comentario(
                destino=destino,
                usuario=request.user,
                comentario=request.data.get("comentario", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino.refresh_from_db()

        return Response(
            _serializar_destino(destino, request)
        )

    # ======================================================
    # DERIVAR
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="derivar",
    )
    def derivar(self, request, pk=None):
        """
        Agrega un nuevo sector al flujo sin reemplazar al sector actual.

        Body:

        {
            "destino_origen": 12,
            "sector_destino": 5,
            "motivo": "Necesitamos verificación de stock"
        }
        """

        pedido = self.get_object()

        destino_origen_id = request.data.get("destino_origen")
        nuevo_sector_id = request.data.get("sector_destino")

        if not destino_origen_id:
            return Response(
                {"detail": "Falta destino_origen."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not nuevo_sector_id:
            return Response(
                {"detail": "Falta sector_destino."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino_origen = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            destino_id=destino_origen_id,
        )

        try:
            nuevo_destino = workflow_service.derivar(
                destino_origen=destino_origen,
                sector_destino=nuevo_sector_id,
                usuario=request.user,
                motivo=request.data.get("motivo", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        nuevo_destino.refresh_from_db()

        return Response(
            _serializar_destino(
                nuevo_destino,
                request,
            ),
            status=status.HTTP_201_CREATED,
        )

    # ======================================================
    # RESOLVER
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="resolver",
    )
    def resolver(self, request, pk=None):
        """
        Body:

        {
            "sector_destino": 3,
            "resultado": "Compra realizada..."
        }
        """

        pedido = self.get_object()

        destino = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            sector_id=request.data.get("sector_destino"),
        )

        try:
            destino = workflow_service.resolver(
                destino=destino,
                usuario=request.user,
                resultado=request.data.get("resultado", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino.refresh_from_db()
        pedido.refresh_from_db()

        return Response({
            "destino": _serializar_destino(
                destino,
                request,
            ),
            "pedido": _serializar_pedido(
                pedido,
                request,
            ),
        })

    # ======================================================
    # RECHAZAR
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="rechazar",
    )
    def rechazar(self, request, pk=None):
        """
        Body:

        {
            "sector_destino": 3,
            "motivo": "No corresponde a este sector"
        }
        """

        pedido = self.get_object()

        destino = self._obtener_destino_usuario(
            pedido=pedido,
            usuario=request.user,
            sector_id=request.data.get("sector_destino"),
        )

        try:
            destino = workflow_service.rechazar(
                destino=destino,
                usuario=request.user,
                motivo=request.data.get("motivo", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        destino.refresh_from_db()
        pedido.refresh_from_db()

        return Response({
            "destino": _serializar_destino(
                destino,
                request,
            ),
            "pedido": _serializar_pedido(
                pedido,
                request,
            ),
        })

    # ======================================================
    # CANCELAR PEDIDO
    # ======================================================

    @action(
        detail=True,
        methods=["post"],
        url_path="cancelar",
    )
    def cancelar(self, request, pk=None):
        """
        Cancela lógicamente el pedido completo.

        Body:

        {
            "motivo": "Pedido generado por error"
        }
        """

        pedido = self.get_object()

        try:
            pedido = workflow_service.cancelar_pedido(
                pedido=pedido,
                usuario=request.user,
                motivo=request.data.get("motivo", ""),
            )
        except ValidationError as exc:
            return Response(
                _error_validacion(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        pedido.refresh_from_db()

        return Response(
            _serializar_pedido(
                pedido,
                request,
            )
        )

    # ======================================================
    # HELPER DE DESTINO
    # ======================================================

    def _obtener_destino_usuario(
        self,
        *,
        pedido,
        usuario,
        sector_id=None,
        destino_id=None,
    ):
        """
        Obtiene un destino perteneciente al pedido y accesible
        para el usuario.

        Para usuarios normales se exige pertenencia activa al sector.

        Staff y superusuarios conservan visibilidad global, pero para
        operar también deben pertenecer activamente al sector destino.
        """

        destinos = (
            PedidoDestino.objects
            .select_related(
                "pedido",
                "sector_destino",
                "responsable",
                "leido_por",
            )
            .filter(pedido=pedido)
        )

        if destino_id is not None:
            destinos = destinos.filter(pk=destino_id)

        if sector_id is not None:
            destinos = destinos.filter(
                sector_destino_id=sector_id
            )

        # Este helper se usa únicamente para acciones operativas. La
        # visibilidad global de staff se resuelve en los querysets de lectura.
        sectores_usuario = _sectores_del_usuario(usuario)

        destinos = destinos.filter(
            sector_destino_id__in=sectores_usuario
        )

        cantidad = destinos.count()

        if cantidad == 0:
            raise PermissionDenied(
                "No existe un destino accesible para ese usuario."
            )

        if cantidad > 1:
            raise DRFValidationError({
                "sector_destino": (
                    "Debe indicar el sector_destino o "
                    "el destino_origen correspondiente."
                )
            })

        return destinos.first()
