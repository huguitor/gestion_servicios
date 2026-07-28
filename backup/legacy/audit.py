"""Orquestación del auditor SQLite legacy, sin escrituras de negocio."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.db.models import NOT_PROVIDED

from .media_reader import (
    LegacyMediaReader,
    MediaAuditError,
    validate_hashes,
)
from .reports import write_reports
from .sqlite_reader import LegacySQLiteReader, SQLiteAuditError


class LegacyAuditError(Exception):
    """El auditor no pudo completar una inspección confiable."""


TABLE_MODEL_MAP = {
    "auth_user": "auth.User",
    "categorias_categoria": "categorias.Categoria",
    "clientes_cliente": "clientes.Cliente",
    "comprobantes_comprobante": "comprobantes.Comprobante",
    "configuracion_configuracionglobal": "configuracion.ConfiguracionGlobal",
    "impuestos_impuesto": "impuestos.Impuesto",
    "marcas_marca": "marcas.Marca",
    "pedidos_pedido": "pedidos.Pedido",
    "pedidos_pedidoitem": "pedidos.PedidoItem",
    "presupuestos_presupuesto": "presupuestos.Presupuesto",
    "presupuestos_presupuestoadjunto": "presupuestos.PresupuestoAdjunto",
    "presupuestos_presupuestoitem": "presupuestos.PresupuestoItem",
    "productos_producto": "productos.Producto",
    "productos_productoimpuesto": "productos.ProductoImpuesto",
    "productos_servicio": "productos.Servicio",
    "productos_servicioimpuesto": "productos.ServicioImpuesto",
    "proveedores_proveedor": "proveedores.Proveedor",
    "remitos_itemremito": "remitos.ItemRemito",
    "remitos_remito": "remitos.Remito",
    "remitos_remitoadjunto": "remitos.RemitoAdjunto",
    "web_clientes_clienteweb": "web_clientes.ClienteWeb",
}

REQUIRED_TABLES = {
    "auth_user",
    "categorias_categoria",
    "clientes_cliente",
    "comprobantes_comprobante",
    "configuracion_configuracionglobal",
    "impuestos_impuesto",
    "marcas_marca",
    "presupuestos_presupuesto",
    "presupuestos_presupuestoadjunto",
    "presupuestos_presupuestoitem",
    "productos_producto",
    "productos_productoimpuesto",
    "productos_servicio",
    "productos_servicioimpuesto",
    "proveedores_proveedor",
    "remitos_itemremito",
    "remitos_remito",
    "remitos_remitoadjunto",
}

MEDIA_FIELDS = {
    "configuracion_configuracionglobal": (
        "logo_principal",
        "logo_favicon",
        "logo_tkinter",
        "imagen_publicitaria_1",
        "imagen_publicitaria_2",
        "imagen_publicitaria_3",
    ),
    "presupuestos_presupuestoadjunto": ("archivo",),
    "productos_producto": ("foto", "plano"),
    "productos_servicio": ("imagen", "adjunto", "video"),
    "remitos_remitoadjunto": ("archivo",),
}

SPECIAL_CONVERSIONS = {
    "presupuestos_presupuestoadjunto": [
        {
            "legacy_fields": ["metadata"],
            "target": "presupuestos.PresupuestoAdjunto.metadata (JSONField)",
            "reason": (
                "SQLite almacena metadata como TEXT; el importador deberá "
                "validar y deserializar JSON antes de asignarlo."
            ),
        }
    ],
    "productos_producto": [
        {
            "legacy_fields": ["foto", "plano"],
            "target": "archivos.Archivo + archivos.ArchivoRelacion",
            "reason": (
                "La multimedia de Producto fue removida del modelo y debe "
                "convertirse al módulo genérico Archivos."
            ),
        }
    ],
}

IGNORED_INFRASTRUCTURE_TABLES = {
    "auth_group",
    "auth_group_permissions",
    "auth_permission",
    "auth_user_groups",
    "auth_user_user_permissions",
    "authtoken_token",
    "django_admin_log",
    "django_content_type",
    "django_migrations",
    "django_session",
}


class LegacyAudit:
    def __init__(
        self,
        *,
        sqlite_path: str | Path,
        media_tar_path: str | Path,
        checksum_manifest_path: str | Path,
        output_root: str | Path,
        run_id: str | None = None,
    ):
        self.sqlite_path = Path(sqlite_path)
        self.media_tar_path = Path(media_tar_path)
        self.checksum_manifest_path = Path(checksum_manifest_path)
        self.output_root = Path(output_root)
        self.run_id = run_id

    def run(self) -> dict:
        try:
            sqlite_reader = LegacySQLiteReader(self.sqlite_path)
            schema = sqlite_reader.inspect()
            references = sqlite_reader.file_references(MEDIA_FIELDS)
            hashes = validate_hashes(
                self.checksum_manifest_path,
                [self.sqlite_path, self.media_tar_path],
            )
            media = LegacyMediaReader(self.media_tar_path).inspect(references)
        except (SQLiteAuditError, MediaAuditError, OSError) as exc:
            raise LegacyAuditError(str(exc)) from exc

        compatibility = self._build_compatibility(schema)
        warnings = self._build_warnings(schema, hashes, media, compatibility)
        blocking = [item for item in warnings if item["severity"] == "error"]
        status = "apto_para_migrar" if not blocking else "requiere_correcciones"
        run_id = self.run_id or self._generate_run_id(hashes)

        summary = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "result": status,
            "sqlite_ok": schema["integrity_ok"] and schema["foreign_keys_ok"],
            "hashes_ok": hashes["ok"],
            "media_ok": media["ok"],
            "table_count": len(schema["tables"]),
            "record_counts": {
                name: table["count"]
                for name, table in schema["tables"].items()
            },
            "foreign_key_count": sum(
                len(table["foreign_keys"])
                for table in schema["tables"].values()
            ),
            "media_file_count": media["file_count"],
            "media_reference_count": media["reference_count"],
            "incompatibility_count": sum(
                item["status"] == "incompatible"
                for item in compatibility["models"]
            ),
            "adaptation_count": sum(
                item["status"] == "requires_adaptation"
                for item in compatibility["models"]
            ),
            "new_fields": compatibility["new_fields"],
            "removed_fields": compatibility["removed_fields"],
            "conversions": compatibility["conversions"],
            "risk_count": len(warnings),
            "blocking_issue_count": len(blocking),
        }
        reports = {
            "summary": summary,
            "schema": schema,
            "compatibility": compatibility,
            "media": {**media, "hashes": hashes},
            "warnings": {"items": warnings},
        }
        output_dir = write_reports(self.output_root, run_id, reports)
        return {
            "run_id": run_id,
            "output_dir": str(output_dir),
            "summary": summary,
            "schema": schema,
            "compatibility": compatibility,
            "media": media,
            "hashes": hashes,
            "warnings": warnings,
        }

    def _build_compatibility(self, schema: dict) -> dict:
        models = []
        all_new_fields = []
        all_removed_fields = []
        all_conversions = []
        found_tables = set(schema["tables"])

        for table_name, model_label in TABLE_MODEL_MAP.items():
            if table_name not in found_tables:
                continue
            table = schema["tables"][table_name]
            model = apps.get_model(model_label)
            legacy_columns = {item["name"]: item for item in table["columns"]}
            current_fields = {
                field.column: field
                for field in model._meta.fields
                if field.concrete
            }
            common_names = sorted(set(legacy_columns) & set(current_fields))
            removed_names = sorted(set(legacy_columns) - set(current_fields))
            added_names = sorted(set(current_fields) - set(legacy_columns))

            new_fields = [
                self._describe_current_field(
                    table_name, model_label, current_fields[name]
                )
                for name in added_names
            ]
            removed_fields = [
                {
                    "table": table_name,
                    "model": model_label,
                    "field": name,
                    "legacy_type": legacy_columns[name]["type"],
                }
                for name in removed_names
            ]
            relation_changes = self._relation_changes(
                table, current_fields, common_names
            )
            conversions = SPECIAL_CONVERSIONS.get(table_name, [])

            converted_legacy_fields = {
                field_name
                for conversion in conversions
                for field_name in conversion["legacy_fields"]
            }
            unexplained_removed = set(removed_names) - converted_legacy_fields
            status = "compatible"
            reasons = []
            if conversions or new_fields or relation_changes:
                status = "requires_adaptation"
            if unexplained_removed:
                status = "incompatible"
                reasons.append(
                    "Hay campos legacy eliminados sin una conversión definida."
                )
            if relation_changes:
                reasons.append("Hay relaciones que requieren adaptación.")
            if conversions:
                reasons.extend(item["reason"] for item in conversions)

            model_result = {
                "table": table_name,
                "model": model_label,
                "record_count": table["count"],
                "status": status,
                "common_fields": common_names,
                "new_fields": new_fields,
                "removed_fields": removed_fields,
                "relation_changes": relation_changes,
                "conversions": conversions,
                "reasons": reasons,
            }
            models.append(model_result)
            all_new_fields.extend(new_fields)
            all_removed_fields.extend(removed_fields)
            all_conversions.extend(
                {"table": table_name, **item} for item in conversions
            )

        missing_required_tables = sorted(REQUIRED_TABLES - found_tables)
        unmapped_tables = sorted(
            found_tables
            - set(TABLE_MODEL_MAP)
            - IGNORED_INFRASTRUCTURE_TABLES
        )
        return {
            "models": models,
            "missing_required_tables": missing_required_tables,
            "unmapped_tables": unmapped_tables,
            "ignored_infrastructure_tables": sorted(
                found_tables & IGNORED_INFRASTRUCTURE_TABLES
            ),
            "new_fields": all_new_fields,
            "removed_fields": all_removed_fields,
            "conversions": all_conversions,
        }

    @staticmethod
    def _describe_current_field(table_name, model_label, field) -> dict:
        has_default = field.default is not NOT_PROVIDED
        return {
            "table": table_name,
            "model": model_label,
            "field": field.column,
            "type": field.get_internal_type(),
            "null": field.null,
            "has_default": has_default,
            "default": (
                "<callable>"
                if has_default and callable(field.default)
                else field.default
                if has_default
                else None
            ),
            "auto_populated": bool(
                getattr(field, "auto_now", False)
                or getattr(field, "auto_now_add", False)
            ),
            "requires_value": bool(
                not field.null
                and not has_default
                and not getattr(field, "auto_now", False)
                and not getattr(field, "auto_now_add", False)
            ),
        }

    @staticmethod
    def _relation_changes(table: dict, current_fields: dict, common_names: list[str]):
        legacy_relations = {
            item["from_column"]: item for item in table["foreign_keys"]
        }
        changes = []
        for column_name in common_names:
            current = current_fields[column_name]
            legacy = legacy_relations.get(column_name)
            if not current.is_relation and not legacy:
                continue
            current_target = (
                current.remote_field.model._meta.db_table
                if current.is_relation
                else None
            )
            legacy_target = legacy["target_table"] if legacy else None
            if current_target != legacy_target:
                changes.append(
                    {
                        "field": column_name,
                        "legacy_target": legacy_target,
                        "current_target": current_target,
                    }
                )
        return changes

    @staticmethod
    def _build_warnings(schema, hashes, media, compatibility) -> list[dict]:
        warnings = []

        def add(code: str, severity: str, message: str, details=None):
            warnings.append(
                {
                    "code": code,
                    "severity": severity,
                    "message": message,
                    "details": details or {},
                }
            )

        if not schema["integrity_ok"]:
            add(
                "sqlite_integrity",
                "error",
                "PRAGMA integrity_check informó errores.",
                {"results": schema["integrity_check"]},
            )
        if not schema["foreign_keys_ok"]:
            add(
                "sqlite_foreign_keys",
                "error",
                "Se encontraron claves foráneas inválidas.",
                {"violations": schema["foreign_key_check"]},
            )
        if not hashes["ok"]:
            add(
                "checksum",
                "error",
                "Uno o más archivos no coinciden con SHA256SUMS.txt.",
                {"files": hashes["files"]},
            )
        if hashes["unused_manifest_entries"]:
            add(
                "unused_manifest_entries",
                "warning",
                "El manifiesto contiene entradas que no forman parte de esta auditoría.",
                {"entries": hashes["unused_manifest_entries"]},
            )
        for code, message, details in (
            ("unsafe_media_path", "El tar contiene rutas inseguras.", media["unsafe_paths"]),
            ("media_symlink", "El tar contiene enlaces simbólicos.", media["symbolic_links"]),
            ("media_hardlink", "El tar contiene hardlinks.", media["hard_links"]),
            ("media_special_entry", "El tar contiene entradas especiales.", media["special_entries"]),
            ("duplicate_media_path", "El tar contiene rutas duplicadas.", media["duplicate_media_paths"]),
            ("missing_media", "Faltan archivos referenciados por SQLite.", media["missing_references"]),
        ):
            if details:
                add(code, "error", message, {"items": details})
        if media["unreferenced_files"]:
            add(
                "unreferenced_media",
                "warning",
                "El tar contiene archivos sin referencia en campos multimedia conocidos.",
                {"items": media["unreferenced_files"]},
            )
        if media["duplicate_contents"]:
            add(
                "duplicate_media_content",
                "warning",
                "El tar contiene archivos con contenido idéntico y rutas distintas.",
                {"groups": media["duplicate_contents"]},
            )
        if compatibility["missing_required_tables"]:
            add(
                "missing_tables",
                "error",
                "Faltan tablas legacy necesarias.",
                {"tables": compatibility["missing_required_tables"]},
            )
        if compatibility["unmapped_tables"]:
            add(
                "unmapped_tables",
                "warning",
                "Hay tablas de negocio sin modelo actual mapeado.",
                {"tables": compatibility["unmapped_tables"]},
            )
        incompatible = [
            item["table"]
            for item in compatibility["models"]
            if item["status"] == "incompatible"
        ]
        if incompatible:
            add(
                "incompatible_models",
                "error",
                "Hay modelos con campos eliminados sin conversión definida.",
                {"tables": incompatible},
            )
        return warnings

    def _generate_run_id(self, hashes: dict) -> str:
        seed = "|".join(
            item["actual_sha256"] or "" for item in hashes["files"]
        )
        suffix = hashlib.sha256(seed.encode()).hexdigest()[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{suffix}"
