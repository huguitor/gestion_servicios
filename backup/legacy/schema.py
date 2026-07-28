"""Contratos inmutables del plan de migración legacy."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ACTION_IMPORT = "import"
ACTION_EXCLUDE = "exclude"
ACTION_GENERATED = "generated"
ACTION_SEQUENCE_REFERENCE = "sequence_reference"

ID_PRESERVE = "preserve"
ID_CURRENT = "current"
ID_GENERATED = "generated"
ID_NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ModelMapping:
    source_table: str | None
    target_model: str | None
    action: str
    id_policy: str
    stage: int | None
    importer: str | None = None
    dependencies: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    removed_fields: tuple[str, ...] = ()
    conversions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StageDefinition:
    number: int
    key: str
    label: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


STAGES = (
    StageDefinition(0, "preconditions", "Precondiciones"),
    StageDefinition(1, "users", "Usuarios"),
    StageDefinition(2, "catalogs", "Configuración y catálogos"),
    StageDefinition(3, "parties", "Clientes y proveedores"),
    StageDefinition(4, "products", "Productos y servicios"),
    StageDefinition(5, "tax_relations", "Relaciones de impuestos"),
    StageDefinition(6, "budgets", "Presupuestos"),
    StageDefinition(7, "budget_items", "Items de presupuesto"),
    StageDefinition(8, "budget_attachments", "Adjuntos de presupuesto"),
    StageDefinition(9, "delivery_notes", "Remitos"),
    StageDefinition(10, "delivery_note_items", "Items de remito"),
    StageDefinition(11, "delivery_note_attachments", "Adjuntos y clientes web"),
    StageDefinition(12, "orders", "Pedidos"),
    StageDefinition(13, "order_items", "Items de pedido"),
    StageDefinition(14, "generic_files", "Conversión multimedia de Producto"),
    StageDefinition(15, "file_fields", "Publicación de media FileField"),
    StageDefinition(16, "admin_history", "Historial de Django Admin"),
    StageDefinition(17, "sequences", "Secuencias PostgreSQL"),
    StageDefinition(18, "final_validation", "Validación integral"),
)


TECHNICAL_TABLES = frozenset(
    {
        "auth_group",
        "auth_group_permissions",
        "auth_permission",
        "auth_user",
        "auth_user_groups",
        "auth_user_user_permissions",
        "authtoken_token",
        "django_admin_log",
        "django_content_type",
        "django_migrations",
        "django_session",
    }
)


TARGET_ONLY_MODELS = (
    "personal.RolPersonal",
    "personal.Cargo",
    "personal.Empleado",
    "archivos.TipoArchivo",
    "archivos.Archivo",
    "archivos.ArchivoRelacion",
    "productos.MovimientoStock",
    "cobranzas.FacturaCobranza",
    "cobranzas.Cobro",
    "cobranzas.SeguimientoCobranza",
    "pedidos_internos.Sector",
    "pedidos_internos.UsuarioSector",
    "pedidos_internos.PedidoInterno",
    "pedidos_internos.PedidoDestino",
    "pedidos_internos.PedidoMovimiento",
    "pedidos_internos.PedidoReglaSLA",
    "pedidos_internos.PedidoInternoDetalle",
)
