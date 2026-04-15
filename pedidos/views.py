# gestion_servicios/pedidos/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Pedido
from .serializers import PedidoSerializer, PedidoDetalleSerializer


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.prefetch_related("items").select_related("cliente", "cliente_web", "cliente_web__user")
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Pedido.objects.prefetch_related("items").select_related(
            "cliente", "cliente_web", "cliente_web__user"
        )

        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        if hasattr(user, "cliente_web"):
            return queryset.filter(cliente_web=user.cliente_web)

        return queryset.none()

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "mis_pedidos"]:
            return PedidoDetalleSerializer
        return PedidoSerializer

    @action(detail=False, methods=["get"])
    def mis_pedidos(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)