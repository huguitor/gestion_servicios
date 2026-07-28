"""Staging controlado y publicación de referencias multimedia legacy."""

from __future__ import annotations

from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction

from archivos.models import Archivo, ArchivoRelacion, TipoArchivo
from archivos.services import FileService
from archivos.services.file_storage import FileStorage
from productos.models import Producto

from .media_reader import normalize_media_path
from .media_staging import MediaStaging


class MediaMigrationError(Exception):
    pass


class LegacyMediaMigrator:
    PRODUCT_ROLES = {"foto": "principal", "plano": "plano"}
    FILE_FIELD_TABLES = {
        "configuracion_configuracionglobal",
        "productos_servicio",
        "presupuestos_presupuestoadjunto",
        "remitos_remitoadjunto",
    }

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
    ):
        self.tar_path = Path(tar_path)
        self.staging = MediaStaging(staging_root, media_root)
        self.references = [item for item in references if item.get("path")]
        self.keep_staging = keep_staging
        self.file_service = file_service
        self.storage = storage
        self.using = using
        self.published_paths = []

    def migrate(self) -> dict:
        report = {
            "found": 0,
            "migrated": 0,
            "missing": [],
            "deduplicated": 0,
            "relations_created": 0,
            "file_fields_published": 0,
            "files": [],
        }
        staged = self.staging.stage(self.tar_path, self.references)
        staged_by_path = {
            item["media_path"]: item for item in staged["files"]
        }
        try:
            with transaction.atomic(using=self.using):
                for reference in self.references:
                    media_path = normalize_media_path(reference["path"])
                    item = staged_by_path.get(media_path)
                    if item is None:
                        report["missing"].append(media_path)
                        raise MediaMigrationError(
                            f"Referencia multimedia faltante: {media_path}"
                        )
                    report["found"] += 1
                    if reference["table"] == "productos_producto":
                        result = self._migrate_product(reference, item)
                        report["deduplicated"] += int(result["deduplicated"])
                        report["relations_created"] += int(
                            result["relation_created"]
                        )
                    elif reference["table"] in self.FILE_FIELD_TABLES:
                        result = self._publish_file_field(media_path, item)
                        report["file_fields_published"] += 1
                    else:
                        raise MediaMigrationError(
                            "Referencia sin política: "
                            f"{reference['table']}.{reference['field']}"
                        )
                    report["migrated"] += 1
                    report["files"].append(
                        {
                            "source": media_path,
                            "sha256": item["sha256"],
                            **result,
                        }
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
        return {"destination": stored, "kind": "file_field"}

    def _migrate_product(self, reference, item):
        role = self.PRODUCT_ROLES.get(reference["field"])
        if role is None:
            raise MediaMigrationError(
                f"Rol de Producto desconocido: {reference['field']}"
            )
        product = Producto.objects.using(self.using).get(
            pk=reference["record_id"]
        )
        content_type = ContentType.objects.db_manager(self.using).get_for_model(
            Producto
        )
        if ArchivoRelacion.objects.using(self.using).filter(
            content_type=content_type,
            object_id=product.pk,
            rol=role,
        ).exists():
            raise MediaMigrationError(
                f"Producto {product.pk} ya posee relación para rol {role}."
            )
        existing = (
            Archivo.objects.using(self.using)
            .filter(checksum=item["sha256"], activo=True)
            .first()
        )
        if existing:
            ArchivoRelacion.objects.using(self.using).create(
                archivo=existing,
                content_type=content_type,
                object_id=product.pk,
                rol=role,
            )
            return {
                "destination": existing.archivo.name,
                "kind": "archivo",
                "deduplicated": True,
                "relation_created": True,
            }
        type_name = (
            "Imagen de producto" if role == "principal" else "Plano de producto"
        )
        folder = "producto-imagen" if role == "principal" else "producto-plano"
        tipo, _ = TipoArchivo.objects.using(self.using).get_or_create(
            nombre=type_name,
            defaults={"carpeta": folder, "activo": True},
        )
        content = ContentFile(
            Path(item["staged_path"]).read_bytes(),
            name=Path(reference["path"]).name,
        )
        result = self.file_service.upload(
            content,
            tipo=tipo,
            content_type=content_type,
            object_id=product.pk,
            rol=role,
        )
        archivo = Archivo.objects.using(self.using).get(pk=result["archivo_id"])
        self.published_paths.append(archivo.archivo.name)
        return {
            "destination": archivo.archivo.name,
            "kind": "archivo",
            "deduplicated": False,
            "relation_created": result["relacion_id"] is not None,
        }

    def _rollback_storage(self):
        errors = []
        for path in reversed(self.published_paths):
            try:
                self.storage.delete(path)
            except Exception as exc:
                errors.append({"path": path, "error": str(exc)})
        return errors
