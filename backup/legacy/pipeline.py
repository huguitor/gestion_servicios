"""Única fuente de verdad del orden ejecutable del importador."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model

from archivos.models import Archivo, ArchivoRelacion, TipoArchivo
from categorias.models import Categoria
from clientes.models import Cliente
from comprobantes.models import Comprobante
from configuracion.models import ConfiguracionGlobal
from impuestos.models import Impuesto
from marcas.models import Marca
from pedidos.models import Pedido, PedidoItem
from presupuestos.models import Presupuesto, PresupuestoAdjunto, PresupuestoItem
from productos.models import Producto, ProductoImpuesto, Servicio, ServicioImpuesto
from proveedores.models import Proveedor
from remitos.models import ItemRemito, Remito, RemitoAdjunto
from web_clientes.models import ClienteWeb

from .importers.admin_history import AdminLogImporter
from .importers.categorias import CategoriasImporter
from .importers.clientes import ClientesImporter
from .importers.comprobantes import ComprobanteImporter
from .importers.configuracion import ConfiguracionImporter
from .importers.impuestos import ImpuestosImporter
from .importers.marcas import MarcasImporter
from .importers.pedidos import PedidosImporter
from .importers.presupuestos import PresupuestosImporter
from .importers.productos import ProductoImpuestoImporter, ProductosImporter
from .importers.proveedores import ProveedoresImporter
from .importers.remitos import RemitosImporter
from .importers.servicios import ServicioImpuestoImporter, ServiciosImporter
from .importers.users import UserImporter
from .importers.web_clientes import ClienteWebImporter


@dataclass(frozen=True)
class PipelineStage:
    key: str
    label: str
    importer: type
    source_tables: tuple[str, ...]


PIPELINE = (
    PipelineStage("users", "Usuarios", UserImporter, ("auth_user",)),
    PipelineStage("configuration", "Configuración", ConfiguracionImporter, ("configuracion_configuracionglobal",)),
    PipelineStage("taxes", "Impuestos", ImpuestosImporter, ("impuestos_impuesto",)),
    PipelineStage("categories", "Categorías", CategoriasImporter, ("categorias_categoria",)),
    PipelineStage("brands", "Marcas", MarcasImporter, ("marcas_marca",)),
    PipelineStage("clients", "Clientes", ClientesImporter, ("clientes_cliente",)),
    PipelineStage("suppliers", "Proveedores", ProveedoresImporter, ("proveedores_proveedor",)),
    PipelineStage("products", "Productos", ProductosImporter, ("productos_producto",)),
    PipelineStage("services", "Servicios", ServiciosImporter, ("productos_servicio",)),
    PipelineStage("product_taxes", "Impuestos de productos", ProductoImpuestoImporter, ("productos_productoimpuesto",)),
    PipelineStage("service_taxes", "Impuestos de servicios", ServicioImpuestoImporter, ("productos_servicioimpuesto",)),
    PipelineStage("receipts", "Comprobantes", ComprobanteImporter, ("comprobantes_comprobante",)),
    PipelineStage("web_clients", "Clientes web", ClienteWebImporter, ("web_clientes_clienteweb",)),
    PipelineStage(
        "budgets",
        "Presupuestos",
        PresupuestosImporter,
        (
            "presupuestos_presupuesto",
            "presupuestos_presupuestoitem",
            "presupuestos_presupuestoadjunto",
        ),
    ),
    PipelineStage(
        "delivery_notes",
        "Remitos",
        RemitosImporter,
        (
            "remitos_remito",
            "remitos_itemremito",
            "remitos_remitoadjunto",
        ),
    ),
    PipelineStage(
        "orders",
        "Pedidos",
        PedidosImporter,
        ("pedidos_pedido", "pedidos_pedidoitem"),
    ),
    PipelineStage("admin_history", "Historial administrativo", AdminLogImporter, ("django_admin_log",)),
)


IMPORTED_MODELS = (
    get_user_model(),
    ConfiguracionGlobal,
    Impuesto,
    Categoria,
    Marca,
    Cliente,
    Proveedor,
    Producto,
    Servicio,
    ProductoImpuesto,
    ServicioImpuesto,
    Comprobante,
    ClienteWeb,
    Presupuesto,
    PresupuestoItem,
    PresupuestoAdjunto,
    Remito,
    ItemRemito,
    RemitoAdjunto,
    Pedido,
    PedidoItem,
    LogEntry,
    TipoArchivo,
    Archivo,
    ArchivoRelacion,
)


def validate_pipeline(manifest) -> None:
    planned = {
        mapping.source_table
        for mapping in manifest.imported_mappings
        if mapping.source_table
    }
    executable = {
        table for stage in PIPELINE for table in stage.source_tables
    }
    if planned != executable:
        missing = sorted(planned - executable)
        extra = sorted(executable - planned)
        raise RuntimeError(
            f"Pipeline incompleto: faltantes={missing}, extra={extra}"
        )
