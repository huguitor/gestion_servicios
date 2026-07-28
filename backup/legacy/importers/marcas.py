from marcas.models import Marca

from .master_base import MasterModelImporter


class MarcasImporter(MasterModelImporter):
    table_name = "marcas_marca"
    model = Marca
    columns = ("id", "nombre", "descripcion", "activo", "creado", "actualizado")
    nullable_fields = frozenset({"descripcion"})
    boolean_fields = frozenset({"activo"})
    unique_fields = ("nombre",)
