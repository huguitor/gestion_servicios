from categorias.models import Categoria
from impuestos.models import Impuesto
from marcas.models import Marca
from productos.models import Servicio, ServicioImpuesto

from .master_base import MasterModelImporter


class ServiciosImporter(MasterModelImporter):
    table_name = "productos_servicio"
    model = Servicio
    columns = (
        "id", "codigo_interno", "nombre", "descripcion", "costo_base",
        "precio_base", "imagen", "video", "adjunto", "activo", "creado",
        "actualizado", "categoria_id", "marca_id", "descripcion_corta",
        "destacado_web", "mostrar_en_home", "orden_web", "publicado_web",
        "slug",
    )
    defaults = {"video": None}
    nullable_fields = frozenset(
        {
            "codigo_interno", "imagen", "video", "adjunto",
            "categoria_id", "marca_id", "slug",
        }
    )
    boolean_fields = frozenset(
        {"activo", "destacado_web", "mostrar_en_home", "publicado_web"}
    )
    integer_fields = frozenset({"orden_web", "categoria_id", "marca_id"})
    decimal_fields = frozenset({"costo_base", "precio_base"})
    unique_fields = ("codigo_interno", "slug")
    foreign_keys = {"categoria_id": Categoria, "marca_id": Marca}


class ServicioImpuestoImporter(MasterModelImporter):
    table_name = "productos_servicioimpuesto"
    model = ServicioImpuesto
    columns = ("id", "tipo", "impuesto_id", "servicio_id")
    timestamp_fields = ()
    integer_fields = frozenset({"impuesto_id", "servicio_id"})
    unique_together = (("servicio_id", "impuesto_id", "tipo"),)
    foreign_keys = {
        "servicio_id": Servicio,
        "impuesto_id": Impuesto,
    }


ServicioImporter = ServiciosImporter
