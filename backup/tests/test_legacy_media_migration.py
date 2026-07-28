import hashlib
import io
import tarfile
import tempfile
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from archivos.models import Archivo, ArchivoRelacion, TipoArchivo
from backup.legacy.media_migration import LegacyMediaMigrator
from productos.models import Producto


def write_tar(path, media_path, content):
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(f"media/{media_path}")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))


class FakeStorage:
    deleted = []

    @classmethod
    def exists(cls, path):
        return False

    @classmethod
    def delete(cls, path):
        cls.deleted.append(path)


class FakeFileService:
    @staticmethod
    def upload(file_obj, *, tipo, content_type, object_id, rol, **kwargs):
        content = file_obj.read()
        archivo = Archivo(
            nombre=file_obj.name,
            nombre_original=file_obj.name,
            archivo=f"archivos/{tipo.carpeta}/{file_obj.name}",
            tipo=tipo,
            mime_type="image/jpeg",
            extension=".jpg",
            tamano_bytes=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
        )
        Archivo.objects.bulk_create([archivo])
        relation = ArchivoRelacion(
            archivo=archivo,
            content_type=content_type,
            object_id=object_id,
            rol=rol,
        )
        ArchivoRelacion.objects.bulk_create([relation])
        return {"archivo_id": archivo.pk, "relacion_id": relation.pk}


class LegacyMediaMigrationTests(TestCase):
    def setUp(self):
        FakeStorage.deleted = []
        Producto.objects.bulk_create(
            [
                Producto(
                    id=7,
                    sku="LEGACY-7",
                    nombre="Producto legacy",
                    precio_venta="10.00",
                    stock=1,
                )
            ]
        )

    def migrate(self, root, content=b"legacy-image"):
        media_path = "productos/foto-7.jpg"
        tar_path = root / "media.tar.gz"
        write_tar(tar_path, media_path, content)
        migrator = LegacyMediaMigrator(
            tar_path=tar_path,
            staging_root=root / "staging",
            media_root=root / "media-root",
            references=[
                {
                    "table": "productos_producto",
                    "record_id": 7,
                    "field": "foto",
                    "path": media_path,
                }
            ],
            file_service=FakeFileService,
            storage=FakeStorage,
        )
        return migrator.migrate()

    def test_creates_archivo_and_relation_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = self.migrate(root)

            relation = ArchivoRelacion.objects.get(object_id=7)
            self.assertEqual(relation.rol, "principal")
            self.assertEqual(relation.content_type.model, "producto")
            self.assertEqual(report["relations_created"], 1)
            self.assertEqual(report["migrated"], 1)
            self.assertFalse((root / "staging").exists())

    def test_deduplicates_by_current_archivo_checksum(self):
        content = b"same-content"
        tipo = TipoArchivo(
            nombre="Existente",
            carpeta="existente",
            activo=True,
        )
        TipoArchivo.objects.bulk_create([tipo])
        existing = Archivo(
            nombre="existente.jpg",
            nombre_original="existente.jpg",
            archivo="archivos/existente/existente.jpg",
            tipo=tipo,
            mime_type="image/jpeg",
            extension=".jpg",
            tamano_bytes=len(content),
            checksum=hashlib.sha256(content).hexdigest(),
        )
        Archivo.objects.bulk_create([existing])

        with tempfile.TemporaryDirectory() as temporary:
            report = self.migrate(Path(temporary), content=content)

        relation = ArchivoRelacion.objects.get(object_id=7)
        self.assertEqual(relation.archivo_id, existing.pk)
        self.assertEqual(Archivo.objects.count(), 1)
        self.assertEqual(report["deduplicated"], 1)
