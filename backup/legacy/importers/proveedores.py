import re

from proveedores.models import Proveedor

from .master_base import MasterImportError, MasterModelImporter


class ProveedoresImporter(MasterModelImporter):
    table_name = "proveedores_proveedor"
    model = Proveedor
    columns = (
        "id", "tipo", "nombre", "documento", "condicion_iva", "telefono",
        "email", "direccion", "ciudad", "provincia", "pais", "activo",
        "creado", "actualizado",
    )
    nullable_fields = frozenset(
        {
            "documento", "telefono", "email", "direccion", "ciudad",
            "provincia",
        }
    )
    boolean_fields = frozenset({"activo"})
    unique_fields = ("documento",)

    def build_instance(self, row):
        instance = super().build_instance(row)
        if instance.documento is not None and not re.fullmatch(
            r"\d{8}|\d{11}", instance.documento
        ):
            raise MasterImportError(
                f"Proveedor {instance.pk}: documento inválido."
            )
        return instance


ProveedorImporter = ProveedoresImporter
