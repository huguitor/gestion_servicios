# gestion/backend/pedidos_internos/api/views.py

from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from licensing.manager import license_manager
from licensing.decorators import require_module

from ..models import (
    Sector,
    PedidoInterno,
    PedidoDestino,
)
from ..services import pedido_service
from .serializers import (
    SectorSerializer,
    PedidoInternoListSerializer,
    PedidoInternoDetalleReadSerializer,
    PedidoInternoCreateSerializer,
    PedidoDestinoSerializer,
)


def _sectores_del_usuario(user):
    """IDs de sectores activos a los que pertenece el usuario."""
    return list(
        user.sectores
        .filter(activo=True)
        .values_list("sector_id", flat=True)
    )


class SectorViewSet(viewsets.ModelViewSet):
    """CRUD de sectores. Lectura para autenticados, escritura solo staff."""
    queryset = Sector.objects.all()
    serializer_class = SectorSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]


class PedidoInternoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not license_manager.is_enabled("pedidos_internos"):
            return PedidoInterno.objects.none()

        qs = (
            PedidoInterno.objects
            .select_related("solicitante", "sector_origen")
            .prefetch_related("detalles", "destinos__sector_destino", "movimientos__usuario")
        )

        user = self.request.user
        if user.is_staff or user.is_superuser:
            return qs

        # Usuario normal: lo que solicitó o lo dirigido a sus sectores.
        sectores = _sectores_del_usuario(user)
        return qs.filter(
            Q(solicitante=user) | Q(destinos__sector_destino_id__in=sectores)
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return PedidoInternoCreateSerializer
        if self.action == "list":
            return PedidoInternoListSerializer
        return PedidoInternoDetalleReadSerializer

    @require_module("pedidos_internos")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @require_module("pedidos_internos")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # ---------- acciones ----------

    @action(detail=False, methods=["get"])
    def mis_pedidos(self, request):
        """Pedidos que solicité yo."""
        qs = self.get_queryset().filter(solicitante=request.user)
        serializer = PedidoInternoListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def bandeja(self, request):
        """
        Pedidos dirigidos a mis sectores (bandeja de entrada).
        Filtros opcionales: ?no_leidos=1, ?pendientes=1.
        """
        sectores = _sectores_del_usuario(request.user)
        destinos = (
            PedidoDestino.objects
            .select_related("sector_destino", "pedido", "pedido__solicitante", "pedido__sector_origen")
            .filter(sector_destino_id__in=sectores)
        )

        if request.query_params.get("no_leidos"):
            destinos = destinos.filter(leido=False)
        if request.query_params.get("pendientes"):
            destinos = destinos.exclude(estado__in=["resuelto", "rechazado"])

        serializer = PedidoDestinoSerializer(destinos, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def marcar_leido(self, request, pk=None):
        """Marca leído el destino del pedido para uno de mis sectores."""
        pedido = self.get_object()
        sectores = _sectores_del_usuario(request.user)

        sector_id = request.data.get("sector_destino")
        destinos = pedido.destinos.filter(sector_destino_id__in=sectores)
        if sector_id:
            destinos = destinos.filter(sector_destino_id=sector_id)

        destino = destinos.first()
        if destino is None:
            return Response(
                {"detail": "No tenés un destino de este pedido en tus sectores."},
                status=status.HTTP_404_NOT_FOUND,
            )

        pedido_service.marcar_leido(destino, request.user)
        return Response(PedidoDestinoSerializer(destino).data)

    @action(detail=True, methods=["post"])
    def derivar(self, request, pk=None):
        """Deriva el pedido a otro sector. Body: {sector_destino, motivo?}."""
        pedido = self.get_object()
        sector_id = request.data.get("sector_destino")
        if not sector_id:
            return Response(
                {"detail": "Falta sector_destino."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sector = get_object_or_404(Sector, pk=sector_id)
        pedido_service.derivar(
            pedido, sector, request.user, motivo=request.data.get("motivo", "")
        )
        pedido.refresh_from_db()
        return Response(PedidoInternoDetalleReadSerializer(pedido, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de la cabecera. Body: {estado, detalle?}."""
        pedido = self.get_object()
        nuevo_estado = request.data.get("estado")
        if not nuevo_estado:
            return Response(
                {"detail": "Falta estado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.core.exceptions import ValidationError
        try:
            pedido_service.cambiar_estado(
                pedido, nuevo_estado, request.user, detalle=request.data.get("detalle", "")
            )
        except ValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        pedido.refresh_from_db()
        return Response(PedidoInternoDetalleReadSerializer(pedido, context={"request": request}).data)
