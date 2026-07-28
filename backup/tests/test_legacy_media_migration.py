import hashlib
import io
import tarfile
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.utils import timezone

from archivos.models import Archivo, ArchivoRelacion
from archivos.services import FileService
from backup.legacy.media_migration import (
    LegacyMediaMigrator,
    MediaMigrationError,
)
from backup.legacy.media_staging import StagingError
from clientes.models import Cliente
from comprobantes.models import Comprobante
from presupuestos.models import Presupuesto, PresupuestoAdjunto
from productos.models import Producto, Servicio


PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def write_tar(path, files):
    with tarfile.open(path, "w:gz") as archive:
        for media_path, content in files.items():
            member = tarfile.TarInfo(f"media/{media_path}")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


class FakeStorage:
    files = set()
    preexisting = set()
    deleted = []

    @classmethod
    def reset(cls):
        cls.files = set()
        cls.preexisting = set()
        cls.deleted = []

    @classmethod
    def exists(cls, path):
        return path in cls.files or path in cls.preexisting

    @classmethod
    def save(cls, file_obj, path):
        cls.files.add(path)
        return path

    @classmethod
    def delete(cls, path):
        cls.deleted.append(path)
        cls.files.discard(path)


class FakeFileService:
    calls = []
    fail = False
    missing_relation = False
    wrong_role = False

    @classmethod
    def reset(cls):
        cls.calls = []
        cls.fail = False
        cls.missing_relation = False
        cls.wrong_role = False

    @classmethod
    def upload_deduplicated(
        cls,
        file_obj,
        *,
        tipo,
        content_type,
        object_id,
        rol,
        **kwargs,
    ):
        cls.calls.append(
            {
                "object_id": object_id,
                "role": rol,
                "method": "upload_deduplicated",
            }
        )
        if cls.fail:
            raise ValueError("FileService failure")
        content = file_obj.read()
        checksum = hashlib.sha256(content).hexdigest()
        archivo = Archivo.objects.filter(checksum=checksum).first()
        created = archivo is None
        if created:
            path = f"archivos/{tipo.carpeta}/{file_obj.name}"
            archivo = Archivo(
                nombre=file_obj.name,
                nombre_original=file_obj.name,
                archivo=path,
                tipo=tipo,
                mime_type="application/pdf",
                extension=".pdf",
                tamano_bytes=len(content),
                checksum=checksum,
            )
            Archivo.objects.bulk_create([archivo])
            FakeStorage.files.add(path)
        relation = ArchivoRelacion.objects.filter(
            archivo=archivo,
            content_type=content_type,
            object_id=object_id,
        ).first()
        relation_created = relation is None
        if relation_created and not cls.missing_relation:
            relation = ArchivoRelacion(
                archivo=archivo,
                content_type=content_type,
                object_id=object_id,
                rol="otro" if cls.wrong_role else rol,
            )
            ArchivoRelacion.objects.bulk_create([relation])
        return {
            "archivo_id": archivo.pk,
            "archivo_path": archivo.archivo.name,
            "relacion_id": 999 if relation is None else relation.pk,
            "checksum": checksum,
            "mime_type": archivo.mime_type,
            "extension": archivo.extension,
            "tamaño_bytes": archivo.tamano_bytes,
            "archivo_created": created,
            "archivo_reused": not created,
            "relation_created": relation_created,
            "relation_reused": not relation_created,
        }


class LegacyMediaMigrationTests(TestCase):
    def setUp(self):
        FakeStorage.reset()
        FakeFileService.reset()
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
        Servicio.objects.bulk_create(
            [
                Servicio(
                    id=8,
                    codigo_interno="SERV-8",
                    nombre="Servicio legacy",
                    costo_base="1.00",
                    precio_base="2.00",
                )
            ]
        )

    def migrate(self, root, references, files, **kwargs):
        tar_path = root / "media.tar.gz"
        write_tar(tar_path, files)
        return LegacyMediaMigrator(
            tar_path=tar_path,
            staging_root=root / "staging",
            media_root=root / "media-root",
            references=references,
            file_service=kwargs.pop("file_service", FakeFileService),
            storage=kwargs.pop("storage", FakeStorage),
            **kwargs,
        ).migrate()

    def product_reference(self):
        return {
            "table": "productos_producto",
            "record_id": 7,
            "field": "foto",
            "path": "productos/foto-7.pdf",
        }

    def test_archivo_only_calls_file_service_and_assigns_correct_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = self.migrate(
                Path(temporary),
                [self.product_reference()],
                {"productos/foto-7.pdf": PDF_CONTENT},
            )

        relation = ArchivoRelacion.objects.get()
        self.assertEqual(FakeFileService.calls[0]["method"], "upload_deduplicated")
        self.assertEqual(relation.rol, "principal")
        self.assertEqual(report["archivos_created"], 1)
        self.assertEqual(report["relations_created"], 1)
        self.assertEqual(report["file_fields_published"], 0)
        self.assertTrue(report["validation"]["ok"])

    def test_repeated_relation_is_reused_not_duplicated(self):
        reference = self.product_reference()
        with tempfile.TemporaryDirectory() as temporary:
            report = self.migrate(
                Path(temporary),
                [reference, reference],
                {"productos/foto-7.pdf": PDF_CONTENT},
            )

        self.assertEqual(Archivo.objects.count(), 1)
        self.assertEqual(ArchivoRelacion.objects.count(), 1)
        self.assertEqual(report["relations_created"], 1)
        self.assertEqual(report["relations_reused"], 1)

    def test_both_policy_publishes_file_field_and_archivo(self):
        reference = {
            "table": "productos_servicio",
            "record_id": 8,
            "field": "imagen",
            "path": "servicios/imagenes/servicio.pdf",
        }
        with tempfile.TemporaryDirectory() as temporary:
            report = self.migrate(
                Path(temporary),
                [reference],
                {reference["path"]: PDF_CONTENT},
            )

        self.assertEqual(report["file_fields_published"], 1)
        self.assertEqual(report["archivos_created"], 1)
        self.assertEqual(ArchivoRelacion.objects.get().rol, "principal")

    def test_missing_required_file_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(StagingError):
                self.migrate(
                    Path(temporary),
                    [self.product_reference()],
                    {"productos/other.pdf": PDF_CONTENT},
                )

    def test_file_service_failure_rolls_back_and_cleans_new_filefield(self):
        FakeFileService.fail = True
        reference = {
            "table": "productos_servicio",
            "record_id": 8,
            "field": "imagen",
            "path": "servicios/imagenes/servicio.pdf",
        }
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "FileService failure"):
                self.migrate(
                    Path(temporary),
                    [reference],
                    {reference["path"]: PDF_CONTENT},
                )

        self.assertEqual(Archivo.objects.count(), 0)
        self.assertIn(reference["path"], FakeStorage.deleted)
        self.assertNotIn(reference["path"], FakeStorage.files)

    def test_cleanup_never_deletes_preexisting_file(self):
        reference = {
            "table": "productos_servicio",
            "record_id": 8,
            "field": "imagen",
            "path": "servicios/imagenes/preexisting.pdf",
        }
        FakeStorage.preexisting.add(reference["path"])
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                MediaMigrationError, "ya existe"
            ):
                self.migrate(
                    Path(temporary),
                    [reference],
                    {reference["path"]: PDF_CONTENT},
                )

        self.assertNotIn(reference["path"], FakeStorage.deleted)
        self.assertIn(reference["path"], FakeStorage.preexisting)

    def test_validation_fails_when_relation_is_missing(self):
        FakeFileService.missing_relation = True
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                MediaMigrationError, "archivo_relacion_missing"
            ):
                self.migrate(
                    Path(temporary),
                    [self.product_reference()],
                    {"productos/foto-7.pdf": PDF_CONTENT},
                )

    def test_validation_fails_when_role_is_wrong(self):
        FakeFileService.wrong_role = True
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                MediaMigrationError, "invalid_role"
            ):
                self.migrate(
                    Path(temporary),
                    [self.product_reference()],
                    {"productos/foto-7.pdf": PDF_CONTENT},
                )


class LegacyMediaFocusedIntegrationTests(TestCase):
    def create_attachments(self, first_path, second_path):
        User = get_user_model()
        User.objects.bulk_create(
            [
                User(
                    id=10,
                    username="legacy-media-test",
                    password="unusable",
                    date_joined=timezone.now(),
                )
            ]
        )
        Cliente.objects.bulk_create(
            [
                Cliente(
                    id=10,
                    tipo="juridica",
                    nombre="Cliente test",
                )
            ]
        )
        Comprobante.objects.bulk_create(
            [
                Comprobante(
                    id=10,
                    tipo="PRES",
                    serie="T",
                    numero_inicial=1,
                    numero_final=10,
                    proximo_numero=1,
                )
            ]
        )
        Presupuesto.objects.bulk_create(
            [
                Presupuesto(
                    id=10,
                    cliente_id=10,
                    creado_por_id=10,
                    comprobante_id=10,
                )
            ]
        )
        PresupuestoAdjunto.objects.bulk_create(
            [
                PresupuestoAdjunto(
                    id=1,
                    presupuesto_id=10,
                    archivo=first_path,
                    tipo="otro",
                    nombre_original="primero.pdf",
                    tamaño=len(PDF_CONTENT),
                    extension="pdf",
                ),
                PresupuestoAdjunto(
                    id=2,
                    presupuesto_id=10,
                    archivo=second_path,
                    tipo="otro",
                    nombre_original="segundo.pdf",
                    tamaño=len(PDF_CONTENT),
                    extension="pdf",
                ),
            ]
        )

    def test_two_identical_attachments_create_one_archivo_two_relations(self):
        first = "presupuestos/adjuntos/primero.pdf"
        second = "presupuestos/adjuntos/segundo.pdf"
        self.create_attachments(first, second)
        references = [
            {
                "table": "presupuestos_presupuestoadjunto",
                "record_id": 1,
                "field": "archivo",
                "path": first,
            },
            {
                "table": "presupuestos_presupuestoadjunto",
                "record_id": 2,
                "field": "archivo",
                "path": second,
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media_root = root / "media"
            tar_path = root / "media.tar.gz"
            write_tar(
                tar_path,
                {first: PDF_CONTENT, second: PDF_CONTENT},
            )
            with override_settings(MEDIA_ROOT=media_root):
                report = LegacyMediaMigrator(
                    tar_path=tar_path,
                    staging_root=root / "staging",
                    media_root=media_root,
                    references=references,
                    file_service=FileService,
                ).migrate()

                archivo = Archivo.objects.get()
                relations = list(
                    ArchivoRelacion.objects.order_by("object_id")
                )
                self.assertTrue(
                    (media_root / first).is_file()
                )
                self.assertTrue(
                    (media_root / second).is_file()
                )
                self.assertTrue(
                    (media_root / archivo.archivo.name).is_file()
                )

            self.assertFalse((root / "staging").exists())

        self.assertEqual(Archivo.objects.count(), 1)
        self.assertEqual(len(relations), 2)
        self.assertEqual(
            [relation.object_id for relation in relations], [1, 2]
        )
        self.assertEqual(
            {relation.rol for relation in relations}, {"adjunto"}
        )
        self.assertEqual(
            archivo.checksum,
            hashlib.sha256(PDF_CONTENT).hexdigest(),
        )
        self.assertEqual(report["deduplicated"], 1)
        self.assertEqual(report["archivos_created"], 1)
        self.assertEqual(report["archivos_reused"], 1)
        self.assertEqual(report["relations_created"], 2)
        self.assertEqual(report["file_fields_published"], 2)
        self.assertTrue(report["validation"]["ok"])
