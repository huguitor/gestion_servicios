"""Runner de infraestructura: preflight y plan, sin importación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from time import perf_counter
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.apps import apps
from django.db import connection as default_connection
from django.db.models import Count, Max, Min, UniqueConstraint

from .manifest import LegacyManifest
from .media_migration import LegacyMediaMigrator
from .media_staging import MediaStaging
from .pipeline import IMPORTED_MODELS, PIPELINE, validate_pipeline
from .planner import LegacyPlanner
from .sequences import PostgresSequenceManager
from .validators import ValidationContext, ValidatorSuite


@dataclass(frozen=True)
class RunnerResult:
    state: str
    audit_run_id: str
    output_dir: str
    validations: tuple[dict, ...]


class LegacyInfrastructureRunner:
    """Abre, valida, planifica y finaliza. Nunca importa registros."""

    def __init__(
        self,
        *,
        audit_dir: str | Path,
        sqlite_path: str | Path,
        media_tar_path: str | Path,
        checksum_manifest_path: str | Path,
        plan_output_root: str | Path | None = None,
        staging_root: str | Path | None = None,
        media_root: str | Path | None = None,
        connection: Any = None,
        validator_suite=None,
        planner=None,
        manifest_loader=LegacyManifest.load,
    ):
        self.audit_dir = Path(audit_dir)
        self.sqlite_path = Path(sqlite_path)
        self.media_tar_path = Path(media_tar_path)
        self.checksum_manifest_path = Path(checksum_manifest_path)
        self.plan_output_root = Path(
            plan_output_root or Path(settings.DATA_DIR_ABS) / "legacy-plan"
        )
        self.staging_root = Path(
            staging_root or Path(settings.DATA_DIR_ABS) / "legacy-staging"
        )
        self.media_root = Path(media_root or settings.MEDIA_ROOT)
        self.connection = connection or default_connection
        self.validator_suite = validator_suite or ValidatorSuite()
        self.planner = planner or LegacyPlanner(self.plan_output_root)
        self.manifest_loader = manifest_loader
        self.state = "initialized"

    def run(self) -> RunnerResult:
        manifest = None
        try:
            manifest = self.manifest_loader(self.audit_dir)
            self.state = "manifest_loaded"
            context = ValidationContext(
                manifest=manifest,
                sqlite_path=self.sqlite_path,
                media_tar_path=self.media_tar_path,
                checksum_manifest_path=self.checksum_manifest_path,
                staging_root=self.staging_root,
                media_root=self.media_root,
                connection=self.connection,
            )
            validation_results = self.validator_suite.run(context)
            self.state = "validated"
            plan_result = self.planner.generate(manifest, validation_results)
            self.state = "finished"
            return RunnerResult(
                state=self.state,
                audit_run_id=manifest.run_id,
                output_dir=plan_result["output_dir"],
                validations=tuple(
                    result.as_dict() for result in validation_results
                ),
            )
        except Exception:
            self.state = "failed"
            raise
        finally:
            if hasattr(self.connection, "close"):
                self.connection.close()


class LegacyMigrationError(Exception):
    pass


class LegacyMigrationRunner:
    """Preflight, plan y aplicación explícita del pipeline completo."""

    def __init__(
        self,
        *,
        audit_dir,
        sqlite_path,
        media_tar_path,
        checksum_manifest_path,
        report_root,
        staging_root,
        media_root=None,
        batch_size=500,
        apply=False,
        allow_production=False,
        keep_staging=False,
        connection=None,
        validator_suite=None,
        planner_factory=LegacyPlanner,
        media_migrator_class=LegacyMediaMigrator,
        sequence_manager_class=PostgresSequenceManager,
        pipeline=PIPELINE,
        production=None,
        manifest_loader=LegacyManifest.load,
        pipeline_validator=validate_pipeline,
    ):
        if allow_production and not apply:
            raise LegacyMigrationError(
                "--allow-production sólo es válido junto con --apply."
            )
        self.audit_dir = Path(audit_dir)
        self.sqlite_path = Path(sqlite_path)
        self.media_tar_path = Path(media_tar_path)
        self.checksum_manifest_path = Path(checksum_manifest_path)
        self.report_root = Path(report_root)
        self.staging_root = Path(staging_root)
        self.media_root = Path(media_root or settings.MEDIA_ROOT)
        self.batch_size = batch_size
        self.apply = apply
        self.allow_production = allow_production
        self.keep_staging = keep_staging
        self.connection = connection or default_connection
        self.validator_suite = validator_suite or ValidatorSuite()
        self.planner_factory = planner_factory
        self.media_migrator_class = media_migrator_class
        self.sequence_manager_class = sequence_manager_class
        self.pipeline = pipeline
        self.production = (not settings.DEBUG) if production is None else production
        self.manifest_loader = manifest_loader
        self.pipeline_validator = pipeline_validator
        self.report = {}

    def run(self):
        started = perf_counter()
        manifest = self.manifest_loader(self.audit_dir)
        self.pipeline_validator(manifest)
        if self.apply and self.production and not self.allow_production:
            raise LegacyMigrationError(
                "Ejecución de escritura rechazada en entorno de producción. "
                "Usá --allow-production tras verificar backups y destino."
            )
        context = ValidationContext(
            manifest=manifest,
            sqlite_path=self.sqlite_path,
            media_tar_path=self.media_tar_path,
            checksum_manifest_path=self.checksum_manifest_path,
            staging_root=self.staging_root / manifest.run_id / "preflight",
            media_root=self.media_root,
            connection=self.connection,
        )
        output_dir = None
        self.report = self._base_report(manifest)
        try:
            validations = self.validator_suite.run(context)
            self.report["validations"] = [
                result.as_dict() for result in validations
            ]
            planner = self.planner_factory(self.report_root)
            plan = planner.generate(
                manifest,
                validations,
                mode="apply" if self.apply else "validation",
            )
            output_dir = Path(plan["output_dir"])
            self.report["plan"] = str(output_dir / "plan.json")
            self.report["report_dir"] = str(output_dir)
            if not self.apply:
                self.report["result"] = "validation_complete_without_writes"
                self.report["duration_seconds"] = round(perf_counter() - started, 6)
                self._write_final(output_dir)
                return self.report

            preserved_references = []
            for stage in self.pipeline:
                stage_started = perf_counter()
                stage_report = {
                    "key": stage.key,
                    "label": stage.label,
                    "status": "running",
                    "source_tables": list(stage.source_tables),
                }
                self.report["stages"].append(stage_report)
                try:
                    importer = stage.importer(
                        self.sqlite_path,
                        batch_size=self.batch_size,
                        using=self.connection.alias,
                    )
                    result = importer.import_all()
                    serialized = self._serialize_result(result)
                    preserved_references.extend(
                        self._collect_references(serialized)
                    )
                    self.report["warnings"].extend(
                        self._collect_named_lists(serialized, "warnings")
                    )
                    stage_report.update(
                        {
                            "status": "completed",
                            "report": serialized,
                            "duration_seconds": round(
                                perf_counter() - stage_started, 6
                            ),
                        }
                    )
                except Exception as exc:
                    stage_report.update(
                        {
                            "status": "rolled_back",
                            "error": str(exc),
                            "duration_seconds": round(
                                perf_counter() - stage_started, 6
                            ),
                        }
                    )
                    raise

            media_started = perf_counter()
            references = self._merge_references(
                manifest.media.get("references", []),
                preserved_references,
            )
            try:
                media = self.media_migrator_class(
                    tar_path=self.media_tar_path,
                    staging_root=self.staging_root / manifest.run_id / "media",
                    media_root=self.media_root,
                    references=references,
                    keep_staging=self.keep_staging,
                    using=self.connection.alias,
                ).migrate()
                self.report["media"] = {
                    **media,
                    "status": "completed",
                    "duration_seconds": round(
                        perf_counter() - media_started, 6
                    ),
                }
                if not media.get("validation", {}).get("ok", False):
                    self.report["media"]["status"] = "validation_failed"
                    raise LegacyMigrationError(
                        "La validación multimedia obligatoria falló."
                    )
            except Exception as exc:
                if self.report["media"].get("status") != "validation_failed":
                    self.report["media"] = {
                        "status": "rolled_back",
                        "error": str(exc),
                        "duration_seconds": round(
                            perf_counter() - media_started, 6
                        ),
                    }
                else:
                    self.report["media"]["error"] = str(exc)
                self.report["media"].update(
                    {
                        "data_state": "imported_domains_committed",
                        "requires_fresh_destination": True,
                    }
                )
                raise

            sequence_started = perf_counter()
            try:
                self.report["sequences"] = self.sequence_manager_class(
                    self.connection
                ).adjust(IMPORTED_MODELS)
            except Exception as exc:
                self.report["sequence_error"] = str(exc)
                raise
            self.report["sequence_duration_seconds"] = round(
                perf_counter() - sequence_started, 6
            )
            self.report["final_validation"] = self._final_validation(manifest)
            self.report["result"] = "migration_completed"
            self.report["duration_seconds"] = round(perf_counter() - started, 6)
            self._write_final(output_dir)
            return self.report
        except Exception as exc:
            self.report["result"] = "migration_failed"
            self.report["errors"].append(str(exc))
            self.report["duration_seconds"] = round(perf_counter() - started, 6)
            if output_dir:
                self._write_final(output_dir)
            raise
        finally:
            preflight_root = self.staging_root / manifest.run_id / "preflight"
            MediaStaging(preflight_root, self.media_root).cleanup()
            if hasattr(self.connection, "close"):
                self.connection.close()

    def _base_report(self, manifest):
        settings_dict = self.connection.settings_dict
        return {
            "version": 1,
            "run_id": manifest.run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "mode": "apply" if self.apply else "validation",
            "source": str(self.sqlite_path.resolve()),
            "destination": {
                "vendor": self.connection.vendor,
                "host": settings_dict.get("HOST") or "",
                "name": settings_dict.get("NAME") or "",
            },
            "hashes": manifest.media.get("hashes", {}),
            "estimated_tables": len(manifest.imported_mappings),
            "estimated_records": sum(
                manifest.source_count(item.source_table)
                for item in manifest.imported_mappings
            ),
            "stages": [],
            "media": {},
            "sequences": [],
            "warnings": [],
            "errors": [],
            "result": "running",
        }

    @staticmethod
    def _serialize_result(result):
        if isinstance(result, dict):
            return {
                key: LegacyMigrationRunner._serialize_result(value)
                for key, value in result.items()
            }
        if hasattr(result, "as_dict"):
            return result.as_dict()
        raise LegacyMigrationError(
            f"Reporte de importador no serializable: {type(result).__name__}"
        )

    @staticmethod
    def _collect_references(payload):
        found = []
        if isinstance(payload, dict):
            refs = payload.get("preserved_references")
            if isinstance(refs, list):
                found.extend(refs)
            for value in payload.values():
                found.extend(LegacyMigrationRunner._collect_references(value))
        elif isinstance(payload, list):
            for value in payload:
                found.extend(LegacyMigrationRunner._collect_references(value))
        return found

    @staticmethod
    def _collect_named_lists(payload, name):
        found = []
        if isinstance(payload, dict):
            value = payload.get(name)
            if isinstance(value, list):
                found.extend(value)
            for nested in payload.values():
                found.extend(
                    LegacyMigrationRunner._collect_named_lists(nested, name)
                )
        elif isinstance(payload, list):
            for nested in payload:
                found.extend(
                    LegacyMigrationRunner._collect_named_lists(nested, name)
                )
        return found

    @staticmethod
    def _merge_references(audited, preserved):
        by_key = {}
        for item in [*audited, *preserved]:
            table = item.get("table") or item.get("source_table")
            record_id = item.get("record_id") or item.get("source_pk")
            field = item.get("field") or item.get("source_field")
            key = (table, record_id, field, item.get("path"))
            by_key[key] = {
                **item,
                "table": table,
                "record_id": record_id,
                "field": field,
            }
        return list(by_key.values())

    def _final_validation(self, manifest):
        results = []
        errors = []
        source_ranges = self._source_pk_ranges(manifest)
        for mapping in manifest.imported_mappings:
            model = apps.get_model(mapping.target_model)
            expected = manifest.source_count(mapping.source_table)
            manager = model._default_manager.using(self.connection.alias)
            actual = manager.count()
            target_range = manager.aggregate(
                minimum=Min(model._meta.pk.name),
                maximum=Max(model._meta.pk.name),
            )
            item = {
                "source_table": mapping.source_table,
                "target_model": mapping.target_model,
                "expected": expected,
                "actual": actual,
                "source_pk_range": source_ranges[mapping.source_table],
                "target_pk_range": target_range,
            }
            item["ok"] = (
                expected == actual
                and item["source_pk_range"]["minimum"]
                == target_range["minimum"]
                and item["source_pk_range"]["maximum"]
                == target_range["maximum"]
            )
            results.append(item)
            if not item["ok"]:
                errors.append(item)
            duplicates = self._unique_duplicates(model)
            if duplicates:
                errors.append(
                    {
                        "target_model": mapping.target_model,
                        "unique_duplicates": duplicates,
                    }
                )
        try:
            self.connection.check_constraints()
        except Exception as exc:
            errors.append({"foreign_key_constraints": str(exc)})
        planned = {
            table for stage in self.pipeline for table in stage.source_tables
        }
        processed = {
            table
            for stage in self.report["stages"]
            if stage["status"] == "completed"
            for table in stage["source_tables"]
        }
        if planned != processed:
            errors.append(
                {
                    "pipeline": "incomplete",
                    "missing": sorted(planned - processed),
                }
            )
        if errors:
            raise LegacyMigrationError(
                f"Validación final falló: {errors}"
            )
        media_ok = (
            not self.report["media"].get("missing")
            and self.report["media"].get("found", 0)
            == self.report["media"].get("migrated", 0)
            and self.report["media"].get(
                "validation", {"ok": True}
            ).get("ok", False)
        )
        if not media_ok:
            raise LegacyMigrationError(
                "Validación final falló para la etapa multimedia."
            )
        return {
            "ok": True,
            "models": results,
            "unprocessed": [],
            "media_ok": True,
            "sequences_verified": len(self.report["sequences"]),
            "foreign_keys_ok": True,
            "unique_constraints_ok": True,
        }

    def _source_pk_ranges(self, manifest):
        ranges = {}
        if not manifest.imported_mappings:
            return ranges
        uri = f"file:{quote(str(self.sqlite_path.resolve()))}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        try:
            for mapping in manifest.imported_mappings:
                table = mapping.source_table.replace('"', '""')
                minimum, maximum = connection.execute(
                    f'SELECT MIN(id), MAX(id) FROM "{table}"'
                ).fetchone()
                ranges[mapping.source_table] = {
                    "minimum": minimum,
                    "maximum": maximum,
                }
        finally:
            connection.close()
        return ranges

    def _unique_duplicates(self, model):
        groups = []
        for field in model._meta.concrete_fields:
            if field.unique and not field.primary_key:
                groups.append((field.name,))
        groups.extend(tuple(fields) for fields in model._meta.unique_together)
        groups.extend(
            tuple(constraint.fields)
            for constraint in model._meta.constraints
            if isinstance(constraint, UniqueConstraint) and constraint.fields
        )
        duplicates = []
        manager = model._default_manager.using(self.connection.alias)
        for fields in dict.fromkeys(groups):
            query = manager.values(*fields).annotate(total=Count("pk"))
            for field_name in fields:
                field = model._meta.get_field(field_name)
                if field.null:
                    query = query.exclude(**{f"{field_name}__isnull": True})
            if query.filter(total__gt=1).exists():
                duplicates.append(list(fields))
        return duplicates

    def _write_final(self, output_dir):
        sanitized = self._sanitize(self.report)
        (output_dir / "migration-report.json").write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        label = {
            "validation_complete_without_writes": "VALIDACIÓN COMPLETA SIN ESCRITURAS",
            "migration_completed": "MIGRACIÓN COMPLETADA",
            "migration_failed": "MIGRACIÓN FALLIDA",
        }.get(self.report["result"], self.report["result"])
        (output_dir / "migration-summary.txt").write_text(
            f"{label}\nRun: {self.report['run_id']}\n"
            f"Modo: {self.report['mode']}\n"
            f"Duración: {self.report.get('duration_seconds', 0)} s\n",
            encoding="utf-8",
        )

    @classmethod
    def _sanitize(cls, value):
        forbidden = ("password", "token", "secret")
        if isinstance(value, dict):
            return {
                key: cls._sanitize(item)
                for key, item in value.items()
                if not any(word in key.lower() for word in forbidden)
            }
        if isinstance(value, list):
            return [cls._sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [cls._sanitize(item) for item in value]
        return value
