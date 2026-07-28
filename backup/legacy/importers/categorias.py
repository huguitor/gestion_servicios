from categorias.models import Categoria

from .master_base import MasterModelImporter


class CategoriasImporter(MasterModelImporter):
    table_name = "categorias_categoria"
    model = Categoria
    columns = ("id", "nombre", "descripcion", "activo", "creado", "actualizado")
    nullable_fields = frozenset({"descripcion"})
    boolean_fields = frozenset({"activo"})
    unique_fields = ("nombre",)
