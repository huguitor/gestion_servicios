from django.contrib.auth import get_user_model
from django.db import transaction

from clientes.models import Cliente
from comprobantes.models import Comprobante
from remitos.models import ItemRemito, Remito, RemitoAdjunto

from .master_base import MasterImportError, MasterModelImporter


User = get_user_model()


class RemitoImporter(MasterModelImporter):
    table_name = "remitos_remito"
    model = Remito
    columns = (
        "id", "numero", "fecha_emision", "fecha_entrega", "origen",
        "destino", "presupuesto_relacionado", "numero_referencia", "estado",
        "creado_por_id", "actualizado", "creado", "observaciones",
        "anulado_por_id", "comprobante_id", "fecha_anulacion",
        "licitacion_orden", "motivo_anulacion", "cliente_id",
    )
    nullable_fields = frozenset(
        {"numero", "fecha_entrega", "anulado_por_id", "fecha_anulacion"}
    )
    integer_fields = frozenset(
        {
            "numero", "creado_por_id", "anulado_por_id", "comprobante_id",
            "cliente_id",
        }
    )
    timestamp_fields = ("actualizado", "creado", "fecha_anulacion")
    date_fields = frozenset({"fecha_emision", "fecha_entrega"})
    foreign_keys = {
        "creado_por_id": User,
        "anulado_por_id": User,
        "comprobante_id": Comprobante,
        "cliente_id": Cliente,
    }


class ItemRemitoImporter(MasterModelImporter):
    table_name = "remitos_itemremito"
    model = ItemRemito
    columns = (
        "id", "cantidad", "unidad_medida", "codigo", "observaciones",
        "orden", "remito_id", "descripcion",
    )
    timestamp_fields = ()
    integer_fields = frozenset({"orden", "remito_id"})
    decimal_fields = frozenset({"cantidad"})
    foreign_keys = {"remito_id": Remito}

    def build_instance(self, row):
        instance = super().build_instance(row)
        if instance.cantidad <= 0:
            raise MasterImportError(
                f"ItemRemito {instance.pk}: cantidad debe ser positiva."
            )
        if not instance.unidad_medida:
            raise MasterImportError(
                f"ItemRemito {instance.pk}: unidad_medida vacía."
            )
        return instance


class RemitoAdjuntoImporter(MasterModelImporter):
    table_name = "remitos_remitoadjunto"
    model = RemitoAdjunto
    columns = (
        "id", "archivo", "tipo", "nombre_original", "descripcion",
        "extension", "fecha_subida", "fecha_modificacion", "remito_id",
        "subido_por_id", "tamaño",
    )
    nullable_fields = frozenset({"subido_por_id"})
    integer_fields = frozenset({"remito_id", "subido_por_id", "tamaño"})
    timestamp_fields = ("fecha_subida", "fecha_modificacion")
    foreign_keys = {"remito_id": Remito, "subido_por_id": User}

    def build_instance(self, row):
        instance = super().build_instance(row)
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


class RemitosImporter:
    """Coordinador atómico: cabecera, detalles y adjuntos."""

    def __init__(self, database_path, *, batch_size=500, using="default"):
        kwargs = {"batch_size": batch_size, "using": using}
        self.using = using
        self.header = RemitoImporter(database_path, **kwargs)
        self.items = ItemRemitoImporter(database_path, **kwargs)
        self.attachments = RemitoAdjuntoImporter(database_path, **kwargs)

    def import_all(self):
        with transaction.atomic(using=self.using):
            return {
                "remitos": self.header.import_all(),
                "items": self.items.import_all(),
                "adjuntos": self.attachments.import_all(),
            }
