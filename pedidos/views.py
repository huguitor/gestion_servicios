# gestion/backend/pedidos/views.py

from django.http import HttpResponse

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Pedido
from .pdf_generator import generar_pdf_pedido, filename_for
from licensing.manager import license_manager
from licensing.decorators import require_module
from .serializers import (
    PedidoSerializer,
    PedidoDetalleSerializer,
    PedidoAdminUpdateSerializer,
)


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.prefetch_related("items").select_related(
        "cliente",
        "cliente_web",
        "cliente_web__user",
    )

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not license_manager.is_enabled(
            "pedidos"
        ):

            return Pedido.objects.none()
        queryset = Pedido.objects.prefetch_related("items").select_related(
            "cliente",
            "cliente_web",
            "cliente_web__user",
        )

        user = self.request.user

        # Admin/staff ve todos los pedidos.
        if user.is_staff or user.is_superuser:
            return queryset

        # Cliente web solo ve sus propios pedidos.
        if hasattr(user, "cliente_web"):
            return queryset.filter(cliente_web=user.cliente_web)

        return queryset.none()

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "mis_pedidos"]:
            return PedidoDetalleSerializer

        if self.action in ["update", "partial_update"]:
            return PedidoAdminUpdateSerializer

        return PedidoSerializer

    @require_module(
        "pedidos"
    )
    def list(
        self,
        request,
        *args,
        **kwargs,
    ):

        return super().list(
            request,
            *args,
            **kwargs,
        )

    def _is_admin_user(self, request):
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))

    def update(self, request, *args, **kwargs):
        return self._admin_update(request, partial=False, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._admin_update(request, partial=True, *args, **kwargs)

    def _admin_update(self, request, partial, *args, **kwargs):
        """
        Actualización administrativa de pedidos.

        IMPORTANTE:
        Los clientes comunes NO pueden cambiar estados ni observaciones internas.
        Solo staff/superuser puede ejecutar PATCH/PUT sobre pedidos.
        """

        if not self._is_admin_user(request):
            return Response(
                {"detail": "No tenés permiso para modificar pedidos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()

        serializer = PedidoAdminUpdateSerializer(
            instance,
            data=request.data,
            partial=partial,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        instance.refresh_from_db()

        response_serializer = PedidoDetalleSerializer(
            instance,
            context=self.get_serializer_context(),
        )

        return Response(response_serializer.data)

    @action(detail=False, methods=["get"])
    def mis_pedidos(self, request):
        user = request.user

        if not hasattr(user, "cliente_web"):
            return Response([])

        queryset = Pedido.objects.prefetch_related("items").select_related(
            "cliente",
            "cliente_web",
            "cliente_web__user",
        ).filter(
            cliente_web=user.cliente_web
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        pedido = self.get_object()

        try:
            pdf = generar_pdf_pedido(pedido)

        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=500,
            )

        response = HttpResponse(
            pdf,
            content_type="application/pdf",
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{filename_for(pedido)}"'
        )

        return response