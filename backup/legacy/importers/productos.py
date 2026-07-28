from categorias.models import Categoria
from impuestos.models import Impuesto
from marcas.models import Marca
from productos.models import Producto, ProductoImpuesto
from proveedores.models import Proveedor

from .master_base import MasterModelImporter


class ProductosImporter(MasterModelImporter):
    table_name = "productos_producto"
    model = Producto
    columns = (
        "id", "sku", "codigo_barras", "nombre", "descripcion",
        "precio_venta", "costo_compra", "stock", "stock_reservado",
        "activo", "creado", "actualizado", "categoria_id", "marca_id",
        "proveedor_id", "descripcion_corta", "destacado_web",
        "mostrar_en_home", "orden_web", "publicado_web", "slug",
    )
    source_only_columns = ("foto", "plano")
    defaults = {"stock_reservado": 0}
    nullable_fields = frozenset(
        {
            "sku", "codigo_barras", "costo_compra", "categoria_id",
            "marca_id", "proveedor_id", "slug",
        }
    )
    boolean_fields = frozenset(
        {"activo", "destacado_web", "mostrar_en_home", "publicado_web"}
    )
    integer_fields = frozenset(
        {
            "stock", "stock_reservado", "orden_web", "categoria_id",
            "marca_id", "proveedor_id",
        }
    )
    decimal_fields = frozenset({"precio_venta", "costo_compra"})
    unique_fields = ("sku", "codigo_barras", "nombre", "slug")
    foreign_keys = {
        "categoria_id": Categoria,
        "marca_id": Marca,
        "proveedor_id": Proveedor,
    }

    def build_instance(self, row):
        instance = super().build_instance(row)
        for field_name, role in (("foto", "principal"), ("plano", "plano")):
            path = row.get(field_name)
            if path:
                self.report.preserved_references.append(
                    {
                        "source_table": self.table_name,
                        "source_pk": instance.pk,
                        "source_field": field_name,
                        "target_role": role,
                        "path": str(path),
                    }
                )
        return instance


class ProductoImpuestoImporter(MasterModelImporter):
    table_name = "productos_productoimpuesto"
    model = ProductoImpuesto
    columns = ("id", "tipo", "impuesto_id", "producto_id")
    timestamp_fields = ()
    integer_fields = frozenset({"impuesto_id", "producto_id"})
    unique_together = (("producto_id", "impuesto_id", "tipo"),)
    foreign_keys = {
        "producto_id": Producto,
        "impuesto_id": Impuesto,
    }


ProductoImporter = ProductosImporter
