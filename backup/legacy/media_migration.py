"""Staging, publicación FileField y conversión a Archivos legacy."""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count

from archivos.models import Archivo, ArchivoRelacion, TipoArchivo
from archivos.services import FileService
from archivos.services.file_storage import FileStorage

from .media_policy import MEDIA_POLICY_BY_KEY
from .media_reader import normalize_media_path
from .media_staging import MediaStaging


class MediaMigrationError(Exception):
    pass


class LegacyMediaMigrator:
    def __init__(
        self,
        *,
        tar_path,
        staging_root,
        media_root,
        references,
        keep_staging=False,
        file_service=FileService,
        storage=FileStorage,
        using="default",
        policies=MEDIA_POLICY_BY_KEY,
    ):
        self.tar_path = Path(tar_path)
        self.staging = MediaStaging(staging_root, media_root)
        self.references = [item for item in references if item.get("path")]
        self.keep_staging = keep_staging
        self.file_service = file_service
        self.storage = storage
        self.using = using
        self.policies = policies
        self.published_paths = []

    def migrate(self) -> dict:
        report = {
            "found": 0,
            "migrated": 0,
            "missing": [],
            "deduplicated": 0,
            "archivos_created": 0,
            "archivos_reused": 0,
            "relations_created": 0,
            "relations_reused": 0,
            "file_fields_published": 0,
            "files": [],
            "validation": {"ok": False},
        }
        staged = self.staging.stage(self.tar_path, self.references)
        staged_by_path = {
            item["media_path"]: item for item in staged["files"]
        }
        try:
            with transaction.atomic(using=self.using):
                for reference in self.references:
                    result = self._migrate_reference(
                        reference,
                        staged_by_path,
                    )
                    report["found"] += 1
                    report["migrated"] += 1
                    report["file_fields_published"] += int(
                        result["file_field"] is not None
                    )
                    archive = result["archivo"]
                    if archive:
                        report["deduplicated"] += int(
                            archive["archivo_reused"]
                        )
                        report["archivos_created"] += int(
                            archive["archivo_created"]
                        )
                        report["archivos_reused"] += int(
                            archive["archivo_reused"]
                        )
                        report["relations_created"] += int(
                            archive["relation_created"]
                        )
                        report["relations_reused"] += int(
                            archive["relation_reused"]
                        )
                    report["files"].append(result)
                report["validation"] = self._validate_results(
                    report["files"]
                )
        except Exception as exc:
            cleanup_errors = self._rollback_storage()
            if cleanup_errors:
                raise MediaMigrationError(
                    "Falló la migración multimedia y el cleanup compensatorio: "
                    f"{cleanup_errors}"
                ) from exc
            raise
        finally:
            if not self.keep_staging:
                self.staging.cleanup()
        return report

    def _migrate_reference(self, reference, staged_by_path):
        table = reference.get("table") or reference.get("source_table")
        field = reference.get("field") or reference.get("source_field")
        record_id = reference.get("record_id") or reference.get("source_pk")
        policy = self.policies.get((table, field))
        if policy is None:
            raise MediaMigrationError(
                f"Referencia sin política: {table}.{field}"
            )
        media_path = normalize_media_path(reference["path"])
        item = staged_by_path.get(media_path)
        if item is None:
            raise MediaMigrationError(
                f"Referencia multimedia faltante: {media_path}"
            )
        model = apps.get_model(policy.target_model)
        try:
            target = model._default_manager.using(self.using).get(
                pk=record_id
            )
        except model.DoesNotExist as exc:
            raise MediaMigrationError(
                f"Destino inexistente para {table}#{record_id}."
            ) from exc

        file_field = None
        if policy.publish_file_field:
            file_field = self._publish_file_field(media_path, item)
        archive = None
        if policy.create_archivo:
            archive = self._create_or_reuse_archivo(
                policy,
                target,
                reference,
                item,
            )
        return {
            "source": media_path,
            "sha256": item["sha256"],
            "table": table,
            "record_id": record_id,
            "field": field,
            "policy": policy.mode,
            "role": policy.role,
            "file_field": file_field,
            "archivo": archive,
        }

    def _publish_file_field(self, media_path, item):
        if self.storage.exists(media_path):
            raise MediaMigrationError(
                f"El destino multimedia ya existe: {media_path}"
            )
        content = ContentFile(
            Path(item["staged_path"]).read_bytes(),
            name=Path(media_path).name,
        )
        stored = self.storage.save(content, media_path)
        if stored != media_path:
            self.storage.delete(stored)
            raise MediaMigrationError(
                f"El storage intentó renombrar {media_path} como {stored}."
            )
        self.published_paths.append(stored)
        return {"destination": stored, "published": True}

    def _create_or_reuse_archivo(
        self,
        policy,
        target,
        reference,
        item,
    ):
        tipo, created = TipoArchivo.objects.using(self.using).get_or_create(
            nombre=policy.type_name,
            defaults={
                "carpeta": policy.folder,
                "activo": True,
            },
        )
        if not created and (
            tipo.carpeta != policy.folder or not tipo.activo
        ):
            raise MediaMigrationError(
                f"TipoArchivo incompatible: {policy.type_name}."
            )
        content_type = ContentType.objects.db_manager(
            self.using
        ).get_for_model(target.__class__)
        original_name = (
            getattr(target, "nombre_original", "")
            or Path(reference["path"]).name
        )
        content = ContentFile(
            Path(item["staged_path"]).read_bytes(),
            name=original_name,
        )
        result = self.file_service.upload_deduplicated(
            content,
            tipo=tipo,
            content_type=content_type,
            object_id=target.pk,
            rol=policy.role,
        )
        if result["checksum"] != item["sha256"]:
            raise MediaMigrationError(
                f"FileService devolvió checksum inválido para {reference['path']}."
            )
        if result["archivo_created"]:
            self.published_paths.append(result["archivo_path"])
        return {
            "archivo_id": result["archivo_id"],
            "archivo_path": result["archivo_path"],
            "relation_id": result["relacion_id"],
            "archivo_created": result["archivo_created"],
            "archivo_reused": result["archivo_reused"],
            "relation_created": result["relation_created"],
            "relation_reused": result["relation_reused"],
            "mime_type": result["mime_type"],
            "extension": result["extension"],
            "size": result["tamaño_bytes"],
            "checksum": result["checksum"],
        }

    def _validate_results(self, results):
        failures = []
        archive_ids = set()
        relation_ids = set()
        for result in results:
            if result["file_field"]:
                destination = result["file_field"]["destination"]
                if not self.storage.exists(destination):
                    failures.append(
                        {
                            "source": result["source"],
                            "error": "file_field_missing",
                        }
                    )
            archive_result = result["archivo"]
            if not archive_result:
                continue
            archive_ids.add(archive_result["archivo_id"])
            relation_ids.add(archive_result["relation_id"])
            archive = Archivo.objects.using(self.using).filter(
                pk=archive_result["archivo_id"],
                checksum=result["sha256"],
                activo=True,
            ).first()
            if archive is None:
                failures.append(
                    {
                        "source": result["source"],
                        "error": "archivo_missing_or_checksum_invalid",
                    }
                )
                continue
            if not self.storage.exists(archive.archivo.name):
                failures.append(
                    {
                        "source": result["source"],
                        "error": "archivo_physical_file_missing",
                    }
                )
            policy = self.policies[(result["table"], result["field"])]
            content_type = ContentType.objects.db_manager(
                self.using
            ).get_for_model(apps.get_model(policy.target_model))
            relation = ArchivoRelacion.objects.using(self.using).filter(
                pk=archive_result["relation_id"],
                archivo_id=archive.pk,
                content_type=content_type,
                object_id=result["record_id"],
            ).first()
            if relation is None:
                failures.append(
                    {
                        "source": result["source"],
                        "error": "archivo_relacion_missing",
                    }
                )
            elif relation.rol != policy.role:
                failures.append(
                    {
                        "source": result["source"],
                        "error": "archivo_relacion_invalid_role",
                        "expected": policy.role,
                        "found": relation.rol,
                    }
                )

        duplicate_checksums = list(
            Archivo.objects.using(self.using)
            .exclude(checksum="")
            .values("checksum")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
        )
        duplicate_relations = list(
            ArchivoRelacion.objects.using(self.using)
            .values("archivo_id", "content_type_id", "object_id")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
        )
        if duplicate_checksums:
            failures.append(
                {
                    "error": "duplicate_archivo_checksums",
                    "items": duplicate_checksums,
                }
            )
        if duplicate_relations:
            failures.append(
                {
                    "error": "duplicate_archivo_relations",
                    "items": duplicate_relations,
                }
            )
        expected_archives = len(
            {
                result["sha256"]
                for result in results
                if result["archivo"] is not None
            }
        )
        if len(archive_ids) != expected_archives:
            failures.append(
                {
                    "error": "archivo_count_mismatch",
                    "expected": expected_archives,
                    "found": len(archive_ids),
                }
            )
        expected_relations = len(
            {
                (
                    result["table"],
                    result["record_id"],
                    result["archivo"]["archivo_id"],
                )
                for result in results
                if result["archivo"] is not None
            }
        )
        if len(relation_ids) != expected_relations:
            failures.append(
                {
                    "error": "archivo_relacion_count_mismatch",
                    "expected": expected_relations,
                    "found": len(relation_ids),
                }
            )
        if failures:
            raise MediaMigrationError(
                f"Validación multimedia obligatoria falló: {failures}"
            )
        return {
            "ok": True,
            "references_checked": len(results),
            "unique_archivos": len(archive_ids),
            "relations": len(relation_ids),
            "failures": [],
        }

    def _rollback_storage(self):
        errors = []
        for path in reversed(self.published_paths):
            try:
                self.storage.delete(path)
            except Exception as exc:
                errors.append({"path": path, "error": str(exc)})
        return errors
