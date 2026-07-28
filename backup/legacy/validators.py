"""Preflight de lectura para el futuro importador legacy."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from django.apps import apps
from django.db.migrations.executor import MigrationExecutor

from .media_reader import LegacyMediaReader, MediaAuditError, validate_hashes
from .media_staging import MediaStaging, StagingError
from .schema import TECHNICAL_TABLES


class PreflightError(Exception):
    """Una precondición bloqueante no se cumple."""

    def __init__(self, code: str, message: str, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class ValidationResult:
    code: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationContext:
    manifest: Any
    sqlite_path: Path
    media_tar_path: Path
    checksum_manifest_path: Path
    staging_root: Path
    media_root: Path
    connection: Any
    sqlite_tables: set[str] = field(default_factory=set)
    postgres_tables: set[str] = field(default_factory=set)


class SQLiteAccessibleValidator:
    code = "sqlite_accessible"

    def validate(self, context: ValidationContext) -> ValidationResult:
        path = context.sqlite_path.resolve()
        if not path.is_file():
            raise PreflightError(self.code, f"No existe SQLite: {path}")
        uri = f"file:{quote(str(path))}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.execute("PRAGMA query_only = ON")
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        except sqlite3.DatabaseError as exc:
            raise PreflightError(
                self.code,
                f"No se pudo abrir SQLite en modo lectura: {exc}",
            ) from exc
        finally:
            if "connection" in locals():
                connection.close()
        if quick_check != "ok":
            raise PreflightError(
                self.code,
                "SQLite no superó PRAGMA quick_check.",
                {"result": quick_check},
            )
        context.sqlite_tables = tables
        return ValidationResult(
            self.code,
            "ok",
            "SQLite accesible en modo read-only.",
            {"table_count": len(tables)},
        )


class PostgreSQLAccessibleValidator:
    code = "postgresql_accessible"

    def validate(self, context: ValidationContext) -> ValidationResult:
        if context.connection.vendor != "postgresql":
            raise PreflightError(
                self.code,
                "La conexión destino no es PostgreSQL.",
                {"vendor": context.connection.vendor},
            )
        try:
            context.connection.ensure_connection()
            with context.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                value = cursor.fetchone()[0]
        except Exception as exc:
            raise PreflightError(
                self.code,
                f"PostgreSQL no está accesible: {exc}",
            ) from exc
        if value != 1:
            raise PreflightError(self.code, "PostgreSQL devolvió una respuesta inválida.")
        return ValidationResult(
            self.code,
            "ok",
            "PostgreSQL accesible.",
            {"vendor": context.connection.vendor},
        )


class MigrationsAppliedValidator:
    code = "migrations_applied"

    def __init__(self, executor_factory: Callable = MigrationExecutor):
        self.executor_factory = executor_factory

    def validate(self, context: ValidationContext) -> ValidationResult:
        try:
            executor = self.executor_factory(context.connection)
            targets = executor.loader.graph.leaf_nodes()
            pending = executor.migration_plan(targets)
        except Exception as exc:
            raise PreflightError(
                self.code,
                f"No se pudo verificar migraciones: {exc}",
            ) from exc
        if pending:
            names = [f"{migration.app_label}.{migration.name}" for migration, _ in pending]
            raise PreflightError(
                self.code,
                "Hay migraciones pendientes.",
                {"pending": names},
            )
        return ValidationResult(self.code, "ok", "Migraciones actuales aplicadas.")


class TechnicalTablesValidator:
    code = "technical_tables"

    def __init__(self, required_tables=TECHNICAL_TABLES):
        self.required_tables = frozenset(required_tables)

    def validate(self, context: ValidationContext) -> ValidationResult:
        try:
            tables = set(context.connection.introspection.table_names())
        except Exception as exc:
            raise PreflightError(
                self.code,
                f"No se pudieron inspeccionar tablas PostgreSQL: {exc}",
            ) from exc
        context.postgres_tables = tables
        missing = sorted(self.required_tables - tables)
        if missing:
            raise PreflightError(
                self.code,
                "Faltan tablas técnicas en PostgreSQL.",
                {"missing": missing},
            )
        return ValidationResult(
            self.code,
            "ok",
            "Tablas técnicas presentes.",
            {"tables": sorted(self.required_tables)},
        )


def current_business_tables() -> set[str]:
    business_apps = {
        "archivos",
        "categorias",
        "clientes",
        "cobranzas",
        "comprobantes",
        "configuracion",
        "impuestos",
        "marcas",
        "pedidos",
        "pedidos_internos",
        "personal",
        "presupuestos",
        "productos",
        "proveedores",
        "remitos",
        "web_clientes",
    }
    tables = {
        model._meta.db_table
        for model in apps.get_models()
        if model._meta.app_label in business_apps and model._meta.managed
    }
    tables.update(
        {
            "auth_group",
            "auth_group_permissions",
            "auth_user",
            "auth_user_groups",
            "auth_user_user_permissions",
            "authtoken_token",
            "django_admin_log",
            "django_session",
        }
    )
    return tables


class BusinessTablesEmptyValidator:
    code = "business_tables_empty"

    def __init__(self, table_provider: Callable[[], set[str]] = current_business_tables):
        self.table_provider = table_provider

    def validate(self, context: ValidationContext) -> ValidationResult:
        available = context.postgres_tables or set(
            context.connection.introspection.table_names()
        )
        expected = self.table_provider()
        missing = sorted(expected - available)
        if missing:
            raise PreflightError(
                self.code,
                "Faltan tablas de negocio actuales.",
                {"missing": missing},
            )
        non_empty = []
        try:
            with context.connection.cursor() as cursor:
                for table_name in sorted(expected):
                    quoted = context.connection.ops.quote_name(table_name)
                    cursor.execute(f"SELECT 1 FROM {quoted} LIMIT 1")
                    if cursor.fetchone() is not None:
                        non_empty.append(table_name)
        except Exception as exc:
            raise PreflightError(
                self.code,
                f"No se pudo verificar que las tablas estén vacías: {exc}",
            ) from exc
        if non_empty:
            raise PreflightError(
                self.code,
                "PostgreSQL contiene datos de negocio.",
                {"non_empty": non_empty},
            )
        return ValidationResult(
            self.code,
            "ok",
            "Tablas de negocio vacías.",
            {"checked": len(expected)},
        )


class StagingAvailableValidator:
    code = "staging_available"

    def validate(self, context: ValidationContext) -> ValidationResult:
        try:
            details = MediaStaging(
                context.staging_root,
                context.media_root,
            ).ensure_available()
        except StagingError as exc:
            raise PreflightError(self.code, str(exc)) from exc
        return ValidationResult(
            self.code,
            "ok",
            "Staging disponible y separado de MEDIA_ROOT.",
            details,
        )


class MediaVerifiableValidator:
    code = "media_verifiable"

    def validate(self, context: ValidationContext) -> ValidationResult:
        try:
            hashes = validate_hashes(
                context.checksum_manifest_path,
                [context.sqlite_path, context.media_tar_path],
            )
        except (MediaAuditError, OSError) as exc:
            raise PreflightError(
                self.code,
                f"No se pudo verificar media: {exc}",
            ) from exc
        if not hashes["ok"]:
            raise PreflightError(
                self.code,
                "Los hashes de entrada no son válidos.",
                {"files": hashes["files"]},
            )
        audited_hashes = {
            item["basename"]: item["actual_sha256"]
            for item in context.manifest.media.get("hashes", {}).get("files", [])
        }
        changed = [
            item["basename"]
            for item in hashes["files"]
            if audited_hashes.get(item["basename"]) != item["actual_sha256"]
        ]
        if changed:
            raise PreflightError(
                self.code,
                "Los archivos ya no coinciden con la auditoría aprobada.",
                {"changed": changed},
            )
        try:
            references = context.manifest.media.get("references", [])
            media = LegacyMediaReader(context.media_tar_path).inspect(references)
        except (MediaAuditError, OSError) as exc:
            raise PreflightError(
                self.code,
                f"No se pudo verificar media: {exc}",
            ) from exc
        if not media["ok"]:
            raise PreflightError(
                self.code,
                "La media no supera las validaciones de seguridad.",
                {
                    "missing_references": media["missing_references"],
                    "unsafe_paths": media["unsafe_paths"],
                    "symbolic_links": media["symbolic_links"],
                    "hard_links": media["hard_links"],
                },
            )
        warnings = []
        if media["duplicate_contents"]:
            warnings.append("duplicate_media_content")
        if hashes["unused_manifest_entries"]:
            warnings.append("unused_manifest_entries")
        return ValidationResult(
            self.code,
            "warning" if warnings else "ok",
            "Media verificable sin extracción.",
            {
                "file_count": media["file_count"],
                "reference_count": media["reference_count"],
                "warnings": warnings,
            },
        )


DEFAULT_VALIDATORS = (
    SQLiteAccessibleValidator,
    PostgreSQLAccessibleValidator,
    MigrationsAppliedValidator,
    TechnicalTablesValidator,
    BusinessTablesEmptyValidator,
    StagingAvailableValidator,
    MediaVerifiableValidator,
)


class ValidatorSuite:
    def __init__(self, validators=None):
        self.validators = [
            validator() if isinstance(validator, type) else validator
            for validator in (validators or DEFAULT_VALIDATORS)
        ]

    def run(self, context: ValidationContext) -> list[ValidationResult]:
        results = []
        for validator in self.validators:
            results.append(validator.validate(context))
        return results
