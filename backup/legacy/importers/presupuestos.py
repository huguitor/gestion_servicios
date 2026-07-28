import json
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.db import transaction

from clientes.models import Cliente
from comprobantes.models import Comprobante
from presupuestos.models import Presupuesto, PresupuestoAdjunto, PresupuestoItem
from productos.models import Producto, Servicio

from .master_base import MasterImportError, MasterModelImporter


User = get_user_model()


class PresupuestoImporter(MasterModelImporter):
    table_name = "presupuestos_presupuesto"
    model = Presupuesto
    columns = (
        "id", "fecha", "valido_hasta", "observaciones", "estado", "creado",
        "actualizado", "cliente_id", "creado_por_id", "comprobante_id",
        "condiciones_comerciales", "iva_porcentaje", "iva_valor", "subtotal",
        "total", "numero", "anulado_por_id", "fecha_anulacion",
        "motivo_anulacion",
    )
    nullable_fields = frozenset(
        {
            "valido_hasta", "comprobante_id", "condiciones_comerciales",
            "numero", "anulado_por_id", "fecha_anulacion",
        }
    )
    integer_fields = frozenset(
        {
            "cliente_id", "creado_por_id", "comprobante_id", "numero",
            "anulado_por_id",
        }
    )
    decimal_fields = frozenset(
        {"iva_porcentaje", "iva_valor", "subtotal", "total"}
    )
    timestamp_fields = ("fecha", "creado", "actualizado", "fecha_anulacion")
    date_fields = frozenset({"valido_hasta"})
    foreign_keys = {
        "cliente_id": Cliente,
        "creado_por_id": User,
        "comprobante_id": Comprobante,
        "anulado_por_id": User,
    }


class PresupuestoItemImporter(MasterModelImporter):
    table_name = "presupuestos_presupuestoitem"
    model = PresupuestoItem
    columns = (
        "id", "descripcion", "cantidad", "precio_unitario",
        "presupuesto_id", "producto_id", "servicio_id", "codigo",
    )
    timestamp_fields = ()
    nullable_fields = frozenset({"producto_id", "servicio_id"})
    integer_fields = frozenset(
        {"cantidad", "presupuesto_id", "producto_id", "servicio_id"}
    )
    decimal_fields = frozenset({"precio_unitario"})
    foreign_keys = {
        "presupuesto_id": Presupuesto,
        "producto_id": Producto,
        "servicio_id": Servicio,
    }

    def build_instance(self, row):
        instance = super().build_instance(row)
        if (instance.producto_id is None) == (instance.servicio_id is None):
            raise MasterImportError(
                f"PresupuestoItem {instance.pk}: debe referenciar exactamente "
                "un producto o servicio."
            )
        return instance


class PresupuestoAdjuntoImporter(MasterModelImporter):
    table_name = "presupuestos_presupuestoadjunto"
    model = PresupuestoAdjunto
    columns = (
        "id", "archivo", "tipo", "nombre_original", "descripcion", "tamaño",
        "extension", "fecha_subida", "fecha_modificacion", "es_publico",
        "version", "checksum", "metadata", "presupuesto_id", "subido_por_id",
    )
    nullable_fields = frozenset({"subido_por_id"})
    boolean_fields = frozenset({"es_publico"})
    integer_fields = frozenset(
        {"tamaño", "version", "presupuesto_id", "subido_por_id"}
    )
    timestamp_fields = ("fecha_subida", "fecha_modificacion")
    foreign_keys = {
        "presupuesto_id": Presupuesto,
        "subido_por_id": User,
    }

    def build_instance(self, row):
        converted = dict(row)
        try:
            metadata = json.loads(row["metadata"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise MasterImportError(
                f"PresupuestoAdjunto {row.get('id')}: metadata JSON inválida."
            ) from exc
        if not isinstance(metadata, dict):
            raise MasterImportError(
                f"PresupuestoAdjunto {row.get('id')}: metadata debe ser objeto."
            )
        converted["metadata"] = metadata
        instance = super().build_instance(converted)
        if instance.archivo:
            self.report.preserved_references.append(
                {
                    "source_table": self.table_name,
                    "source_pk": instance.pk,
                    "source_field": "archivo",
                    "path": instance.archivo.name,
                }
            )
        return instance

    def convert_value(self, field_name, value):
        if field_name == "metadata":
            return value
        return super().convert_value(field_name, value)


class PresupuestosImporter:
    """Coordinador atómico: cabecera, detalles y adjuntos."""

    def __init__(self, database_path, *, batch_size=500, using="default"):
        kwargs = {
            "batch_size": batch_size,
            "using": using,
        }
        self.using = using
        self.header = PresupuestoImporter(database_path, **kwargs)
        self.items = PresupuestoItemImporter(database_path, **kwargs)
        self.attachments = PresupuestoAdjuntoImporter(database_path, **kwargs)

    def import_all(self):
        with transaction.atomic(using=self.using):
            reports = {
                "presupuestos": self.header.import_all(),
                "items": self.items.import_all(),
                "adjuntos": self.attachments.import_all(),
            }
            for presupuesto in Presupuesto.objects.using(self.using).all():
                calculated_subtotal = sum(
                    (item.subtotal for item in presupuesto.items.all()),
                    Decimal("0.00"),
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                calculated_iva = (
                    calculated_subtotal
                    * presupuesto.iva_porcentaje
                    / Decimal("100.00")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                calculated_total = calculated_subtotal + calculated_iva
                if (
                    presupuesto.subtotal != calculated_subtotal
                    or presupuesto.iva_valor != calculated_iva
                    or presupuesto.total != calculated_total
                ):
                    self.header.report.warnings.append(
                        {
                            "code": "historical_total_difference",
                            "pk": presupuesto.pk,
                            "legacy": {
                                "subtotal": str(presupuesto.subtotal),
                                "iva": str(presupuesto.iva_valor),
                                "total": str(presupuesto.total),
                            },
                            "calculated": {
                                "subtotal": str(calculated_subtotal),
                                "iva": str(calculated_iva),
                                "total": str(calculated_total),
                            },
                        }
                    )
            return reports
