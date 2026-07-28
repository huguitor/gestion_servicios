from impuestos.models import Impuesto

from .master_base import MasterImportError, MasterModelImporter


class ImpuestosImporter(MasterModelImporter):
    table_name = "impuestos_impuesto"
    model = Impuesto
    columns = (
        "id", "nombre", "porcentaje", "tipo",
        "actualizado", "creado", "display_name",
    )
    nullable_fields = frozenset({"display_name"})
    decimal_fields = frozenset({"porcentaje"})
    unique_fields = ("nombre",)

    def build_instance(self, row):
        instance = super().build_instance(row)
        if instance.porcentaje < 0:
            raise MasterImportError("porcentaje no puede ser negativo.")
        return instance
