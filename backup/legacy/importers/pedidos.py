from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from clientes.models import Cliente
from pedidos.models import Pedido, PedidoItem
from productos.models import Producto, Servicio
from web_clientes.models import ClienteWeb

from .master_base import MasterImportError, MasterModelImporter


class PedidoImporter(MasterModelImporter):
    table_name = "pedidos_pedido"
    model = Pedido
    columns = (
        "id", "estado", "observaciones_cliente", "observaciones_internas",
        "subtotal", "total", "activo", "stock_reservado_aplicado",
        "stock_finalizado_aplicado", "creado", "actualizado", "cliente_id",
        "cliente_web_id",
    )
    defaults = {
        "stock_reservado_aplicado": False,
        "stock_finalizado_aplicado": False,
    }
    nullable_fields = frozenset({"cliente_id", "cliente_web_id"})
    boolean_fields = frozenset(
        {
            "activo", "stock_reservado_aplicado",
            "stock_finalizado_aplicado",
        }
    )
    integer_fields = frozenset({"cliente_id", "cliente_web_id"})
    decimal_fields = frozenset({"subtotal", "total"})
    foreign_keys = {"cliente_id": Cliente, "cliente_web_id": ClienteWeb}

    def build_instance(self, row):
        instance = super().build_instance(row)
        if instance.cliente_id is None and instance.cliente_web_id is None:
            raise MasterImportError(
                f"Pedido {instance.pk}: no posee identidad de cliente."
            )
        return instance


class PedidoItemImporter(MasterModelImporter):
    table_name = "pedidos_pedidoitem"
    model = PedidoItem
    columns = (
        "id", "tipo_item", "nombre_snapshot", "codigo_snapshot",
        "precio_unitario_snapshot", "cantidad", "subtotal", "pedido_id",
        "producto_id", "servicio_id",
    )
    timestamp_fields = ()
    nullable_fields = frozenset({"producto_id", "servicio_id"})
    integer_fields = frozenset(
        {"cantidad", "pedido_id", "producto_id", "servicio_id"}
    )
    decimal_fields = frozenset({"precio_unitario_snapshot", "subtotal"})
    foreign_keys = {
        "pedido_id": Pedido,
        "producto_id": Producto,
        "servicio_id": Servicio,
    }

    def build_instance(self, row):
        instance = super().build_instance(row)
        product = instance.producto_id is not None
        service = instance.servicio_id is not None
        if product == service:
            raise MasterImportError(
                f"PedidoItem {instance.pk}: debe referenciar exactamente "
                "un producto o servicio."
            )
        if (product and instance.tipo_item != "mercaderia") or (
            service and instance.tipo_item != "servicio"
        ):
            raise MasterImportError(
                f"PedidoItem {instance.pk}: tipo_item no coincide con la FK."
            )
        calculated = (
            instance.precio_unitario_snapshot * instance.cantidad
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if instance.subtotal != calculated:
            self.report.warnings.append(
                {
                    "code": "historical_subtotal_difference",
                    "pk": instance.pk,
                    "legacy": str(instance.subtotal),
                    "calculated": str(calculated),
                }
            )
        return instance


class PedidosImporter:
    """Coordinador atómico: pedidos y detalles, sin movimientos de stock."""

    def __init__(self, database_path, *, batch_size=500, using="default"):
        kwargs = {"batch_size": batch_size, "using": using}
        self.using = using
        self.header = PedidoImporter(database_path, **kwargs)
        self.items = PedidoItemImporter(database_path, **kwargs)

    def import_all(self):
        with transaction.atomic(using=self.using):
            reports = {
                "pedidos": self.header.import_all(),
                "items": self.items.import_all(),
            }
            for pedido in Pedido.objects.using(self.using).all():
                calculated = sum(
                    (item.subtotal for item in pedido.items.all()),
                    Decimal("0.00"),
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if pedido.subtotal != calculated or pedido.total != calculated:
                    self.header.report.warnings.append(
                        {
                            "code": "historical_total_difference",
                            "pk": pedido.pk,
                            "legacy": {
                                "subtotal": str(pedido.subtotal),
                                "total": str(pedido.total),
                            },
                            "calculated": str(calculated),
                        }
                    )
            return reports
