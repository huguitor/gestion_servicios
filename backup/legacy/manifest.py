"""Manifest aprobado: mapa definitivo entre SQLite y Django actual."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import (
    ACTION_EXCLUDE,
    ACTION_GENERATED,
    ACTION_IMPORT,
    ACTION_SEQUENCE_REFERENCE,
    ID_CURRENT,
    ID_GENERATED,
    ID_NOT_APPLICABLE,
    ID_PRESERVE,
    ModelMapping,
    STAGES,
    TARGET_ONLY_MODELS,
)


class ManifestError(Exception):
    """El manifest o la auditoría aprobada no son utilizables."""


def _import(
    source: str,
    target: str,
    stage: int,
    importer: str | None,
    *,
    dependencies=(),
    defaults=None,
    removed_fields=(),
    conversions=(),
    notes=(),
) -> ModelMapping:
    return ModelMapping(
        source_table=source,
        target_model=target,
        action=ACTION_IMPORT,
        id_policy=ID_PRESERVE,
        stage=stage,
        importer=importer,
        dependencies=tuple(dependencies),
        defaults=defaults or {},
        removed_fields=tuple(removed_fields),
        conversions=tuple(conversions),
        notes=tuple(notes),
    )


MODEL_MAPPINGS = (
    _import("auth_user", "auth.User", 1, "users.UserImporter"),
    _import("configuracion_configuracionglobal", "configuracion.ConfiguracionGlobal", 2, None),
    _import("impuestos_impuesto", "impuestos.Impuesto", 2, None),
    _import("categorias_categoria", "categorias.Categoria", 2, None),
    _import("marcas_marca", "marcas.Marca", 2, None),
    _import(
        "comprobantes_comprobante",
        "comprobantes.Comprobante",
        2,
        "comprobantes.ComprobanteImporter",
    ),
    _import(
        "clientes_cliente",
        "clientes.Cliente",
        3,
        "clientes.ClienteImporter",
        defaults={"plazo_cobro_dias": 0},
    ),
    _import(
        "proveedores_proveedor",
        "proveedores.Proveedor",
        3,
        "proveedores.ProveedorImporter",
    ),
    _import(
        "productos_producto",
        "productos.Producto",
        4,
        "productos.ProductoImporter",
        dependencies=("proveedores_proveedor", "categorias_categoria", "marcas_marca"),
        defaults={"stock_reservado": 0},
        removed_fields=("foto", "plano"),
        conversions=(
            "foto -> archivos.Archivo + ArchivoRelacion(rol=principal)",
            "plano -> archivos.Archivo + ArchivoRelacion(rol=plano)",
        ),
    ),
    _import(
        "productos_servicio",
        "productos.Servicio",
        4,
        "servicios.ServicioImporter",
        dependencies=("categorias_categoria", "marcas_marca"),
        defaults={"video": None},
    ),
    _import(
        "productos_productoimpuesto",
        "productos.ProductoImpuesto",
        5,
        "productos.ProductoImpuestoImporter",
        dependencies=("productos_producto", "impuestos_impuesto"),
    ),
    _import(
        "productos_servicioimpuesto",
        "productos.ServicioImpuesto",
        5,
        "servicios.ServicioImpuestoImporter",
        dependencies=("productos_servicio", "impuestos_impuesto"),
    ),
    _import(
        "presupuestos_presupuesto",
        "presupuestos.Presupuesto",
        6,
        "presupuestos.PresupuestoImporter",
        dependencies=("clientes_cliente", "auth_user", "comprobantes_comprobante"),
        notes=("No ejecutar Presupuesto.save().",),
    ),
    _import(
        "presupuestos_presupuestoitem",
        "presupuestos.PresupuestoItem",
        7,
        "presupuestos.PresupuestoItemImporter",
        dependencies=(
            "presupuestos_presupuesto",
            "productos_producto",
            "productos_servicio",
        ),
    ),
    _import(
        "presupuestos_presupuestoadjunto",
        "presupuestos.PresupuestoAdjunto",
        8,
        "presupuestos.PresupuestoAdjuntoImporter",
        dependencies=("presupuestos_presupuesto", "auth_user"),
        conversions=("metadata TEXT -> JSONField",),
    ),
    _import(
        "remitos_remito",
        "remitos.Remito",
        9,
        "remitos.RemitoImporter",
        dependencies=("clientes_cliente", "auth_user", "comprobantes_comprobante"),
        notes=("No ejecutar Remito.save().",),
    ),
    _import(
        "remitos_itemremito",
        "remitos.ItemRemito",
        10,
        "remitos.ItemRemitoImporter",
        dependencies=("remitos_remito",),
        conversions=("cantidad SQLite -> Decimal exacto",),
    ),
    _import(
        "remitos_remitoadjunto",
        "remitos.RemitoAdjunto",
        11,
        "remitos.RemitoAdjuntoImporter",
        dependencies=("remitos_remito", "auth_user"),
    ),
    _import(
        "web_clientes_clienteweb",
        "web_clientes.ClienteWeb",
        11,
        "web_clientes.ClienteWebImporter",
        dependencies=("auth_user", "clientes_cliente"),
    ),
    _import(
        "pedidos_pedido",
        "pedidos.Pedido",
        12,
        "pedidos.PedidoImporter",
        dependencies=("clientes_cliente", "web_clientes_clienteweb"),
        defaults={
            "stock_reservado_aplicado": False,
            "stock_finalizado_aplicado": False,
        },
    ),
    _import(
        "pedidos_pedidoitem",
        "pedidos.PedidoItem",
        13,
        "pedidos.PedidoItemImporter",
        dependencies=("pedidos_pedido", "productos_producto", "productos_servicio"),
    ),
    _import(
        "django_admin_log",
        "admin.LogEntry",
        16,
        None,
        dependencies=("auth_user",),
        conversions=("content_type_id legacy -> ContentType actual por app_label/model",),
    ),
    ModelMapping(
        "auth_group",
        "auth.Group",
        ACTION_EXCLUDE,
        ID_CURRENT,
        None,
        notes=("La fuente auditada contiene 0 filas.",),
    ),
    ModelMapping("auth_group_permissions", None, ACTION_EXCLUDE, ID_CURRENT, None),
    ModelMapping("auth_user_groups", None, ACTION_EXCLUDE, ID_CURRENT, None),
    ModelMapping("auth_user_user_permissions", None, ACTION_EXCLUDE, ID_CURRENT, None),
    ModelMapping("auth_permission", "auth.Permission", ACTION_GENERATED, ID_CURRENT, None),
    ModelMapping(
        "django_content_type",
        "contenttypes.ContentType",
        ACTION_GENERATED,
        ID_CURRENT,
        None,
    ),
    ModelMapping("django_migrations", None, ACTION_GENERATED, ID_CURRENT, None),
    ModelMapping("authtoken_token", "authtoken.Token", ACTION_EXCLUDE, ID_NOT_APPLICABLE, None),
    ModelMapping("django_session", "sessions.Session", ACTION_EXCLUDE, ID_NOT_APPLICABLE, None),
    ModelMapping("sqlite_sequence", None, ACTION_SEQUENCE_REFERENCE, ID_NOT_APPLICABLE, 17),
    ModelMapping(
        None,
        "archivos.TipoArchivo",
        ACTION_GENERATED,
        ID_GENERATED,
        14,
        importer="archivos.ArchivoImporter",
    ),
    ModelMapping(
        None,
        "archivos.Archivo",
        ACTION_GENERATED,
        ID_GENERATED,
        14,
        importer="archivos.ArchivoImporter",
    ),
    ModelMapping(
        None,
        "archivos.ArchivoRelacion",
        ACTION_GENERATED,
        ID_GENERATED,
        14,
        importer="archivos.ArchivoImporter",
    ),
)


REQUIRED_AUDIT_FILES = (
    "summary.json",
    "schema.json",
    "compatibility.json",
    "media.json",
    "warnings.json",
)


@dataclass(frozen=True)
class LegacyManifest:
    audit_dir: Path
    summary: dict[str, Any]
    schema: dict[str, Any]
    compatibility: dict[str, Any]
    media: dict[str, Any]
    warnings: dict[str, Any]
    mappings: tuple[ModelMapping, ...] = MODEL_MAPPINGS

    @classmethod
    def load(cls, audit_dir: str | Path) -> "LegacyManifest":
        directory = Path(audit_dir).resolve()
        if not directory.is_dir():
            raise ManifestError(f"No existe el directorio de auditoría: {directory}")
        payloads = {}
        for filename in REQUIRED_AUDIT_FILES:
            path = directory / filename
            if not path.is_file():
                raise ManifestError(f"Falta el informe requerido: {filename}")
            try:
                payloads[filename] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ManifestError(f"Informe inválido {filename}: {exc}") from exc
        if payloads["summary.json"].get("result") != "apto_para_migrar":
            raise ManifestError("La auditoría no está aprobada para migrar.")
        manifest = cls(
            audit_dir=directory,
            summary=payloads["summary.json"],
            schema=payloads["schema.json"],
            compatibility=payloads["compatibility.json"],
            media=payloads["media.json"],
            warnings=payloads["warnings.json"],
        )
        manifest.validate_mapping()
        return manifest

    def validate_mapping(self) -> None:
        source_tables = set(self.schema.get("tables", {}))
        mapped_sources = {
            mapping.source_table
            for mapping in self.mappings
            if mapping.source_table and mapping.source_table != "sqlite_sequence"
        }
        missing = source_tables - mapped_sources
        if missing:
            raise ManifestError(
                "El manifest no define política para: " + ", ".join(sorted(missing))
            )

    @property
    def run_id(self) -> str:
        return str(self.summary["run_id"])

    @property
    def imported_mappings(self) -> tuple[ModelMapping, ...]:
        return tuple(
            mapping for mapping in self.mappings if mapping.action == ACTION_IMPORT
        )

    def source_count(self, table_name: str | None) -> int:
        if not table_name:
            return 0
        return int(self.schema.get("tables", {}).get(table_name, {}).get("count", 0))

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "audit_run_id": self.run_id,
            "mappings": [mapping.as_dict() for mapping in self.mappings],
            "stages": [stage.as_dict() for stage in STAGES],
            "target_only_models": list(TARGET_ONLY_MODELS),
        }
