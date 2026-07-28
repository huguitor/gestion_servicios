import hashlib
import io
import json
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from backup.legacy import LegacyAudit, LegacyAuditError
from backup.legacy.audit import REQUIRED_TABLES


class LegacyAuditTests(SimpleTestCase):
    databases = set()

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.sqlite_path = self.root / "database.sqlite3"
        self.media_path = self.root / "media.tar.gz"
        self.checksums_path = self.root / "SHA256SUMS.txt"
        self.output_root = self.root / "reports"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_corrupt_sqlite_is_rejected(self):
        self.sqlite_path.write_bytes(b"esto no es sqlite")
        self._write_tar({})
        self._write_manifest()

        with self.assertRaisesRegex(LegacyAuditError, "corrupta"):
            self._audit()

    def test_incorrect_hash_requires_corrections(self):
        self._write_schema()
        self._write_tar({})
        self._write_manifest(sqlite_hash="0" * 64)

        result = self._audit()

        self.assertFalse(result["summary"]["hashes_ok"])
        self.assertEqual(
            result["summary"]["result"],
            "requiere_correcciones",
        )
        self.assertIn(
            "checksum",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_missing_referenced_media_requires_corrections(self):
        self._write_schema(
            extra_sql=[
                """
                ALTER TABLE productos_servicio ADD COLUMN imagen varchar(100)
                """,
                """
                INSERT INTO productos_servicio (id, imagen)
                VALUES (1, 'servicios/imagenes/faltante.png')
                """,
            ]
        )
        self._write_tar({})
        self._write_manifest()

        result = self._audit()

        self.assertEqual(
            result["media"]["missing_references"],
            ["servicios/imagenes/faltante.png"],
        )
        self.assertEqual(
            result["summary"]["result"],
            "requiere_correcciones",
        )

    def test_invalid_foreign_key_is_reported(self):
        self._write_schema(
            extra_sql=[
                "CREATE TABLE audit_parent (id INTEGER PRIMARY KEY)",
                """
                CREATE TABLE audit_child (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER NOT NULL
                        REFERENCES audit_parent(id)
                )
                """,
                "INSERT INTO audit_child (id, parent_id) VALUES (1, 999)",
            ]
        )
        self._write_tar({})
        self._write_manifest()

        result = self._audit()

        self.assertFalse(result["summary"]["sqlite_ok"])
        self.assertTrue(result["schema"]["foreign_key_check"])
        self.assertIn(
            "sqlite_foreign_keys",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_missing_required_table_is_reported(self):
        missing_table = "clientes_cliente"
        self._write_schema(excluded_tables={missing_table})
        self._write_tar({})
        self._write_manifest()

        result = self._audit()

        self.assertIn(
            missing_table,
            result["compatibility"]["missing_required_tables"],
        )
        self.assertEqual(
            result["summary"]["result"],
            "requiere_correcciones",
        )

    def test_safe_complete_audit_writes_exact_report_set(self):
        self._write_schema()
        self._write_tar({})
        self._write_manifest()

        result = self._audit()

        self.assertEqual(result["summary"]["result"], "apto_para_migrar")
        output_dir = Path(result["output_dir"])
        self.assertEqual(
            {path.name for path in output_dir.iterdir()},
            {
                "summary.json",
                "schema.json",
                "compatibility.json",
                "media.json",
                "warnings.json",
            },
        )
        summary = json.loads((output_dir / "summary.json").read_text())
        self.assertEqual(summary["run_id"], "test-run")

    def test_tar_links_and_traversal_are_rejected_without_extraction(self):
        self._write_schema()
        with tarfile.open(self.media_path, "w:gz") as archive:
            traversal = tarfile.TarInfo("../../fuera.txt")
            traversal.size = 4
            archive.addfile(traversal, io.BytesIO(b"test"))
            symlink = tarfile.TarInfo("data/media/enlace")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "/etc/passwd"
            archive.addfile(symlink)
            hardlink = tarfile.TarInfo("data/media/hardlink")
            hardlink.type = tarfile.LNKTYPE
            hardlink.linkname = "data/media/origen"
            archive.addfile(hardlink)
        self._write_manifest()

        result = self._audit()

        self.assertTrue(result["media"]["unsafe_paths"])
        self.assertTrue(result["media"]["symbolic_links"])
        self.assertTrue(result["media"]["hard_links"])
        self.assertEqual(
            result["summary"]["result"],
            "requiere_correcciones",
        )

    def test_duplicate_file_content_is_reported_as_warning(self):
        self._write_schema()
        self._write_tar(
            {
                "data/media/uno/documento.pdf": b"mismo contenido",
                "data/media/dos/copia.pdf": b"mismo contenido",
            }
        )
        self._write_manifest()

        result = self._audit()

        self.assertEqual(len(result["media"]["duplicate_contents"]), 1)
        self.assertIn(
            "duplicate_media_content",
            {warning["code"] for warning in result["warnings"]},
        )

    def _audit(self):
        return LegacyAudit(
            sqlite_path=self.sqlite_path,
            media_tar_path=self.media_path,
            checksum_manifest_path=self.checksums_path,
            output_root=self.output_root,
            run_id="test-run",
        ).run()

    def _write_schema(self, *, excluded_tables=None, extra_sql=None):
        excluded_tables = excluded_tables or set()
        connection = sqlite3.connect(self.sqlite_path)
        try:
            for table_name in sorted(REQUIRED_TABLES - excluded_tables):
                connection.execute(
                    f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY)'
                )
            for statement in extra_sql or []:
                connection.execute(statement)
            connection.commit()
        finally:
            connection.close()

    def _write_tar(self, files):
        with tarfile.open(self.media_path, "w:gz") as archive:
            for name, content in files.items():
                data = content.encode() if isinstance(content, str) else content
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def _write_manifest(self, sqlite_hash=None, media_hash=None):
        sqlite_hash = sqlite_hash or self._sha256(self.sqlite_path)
        media_hash = media_hash or self._sha256(self.media_path)
        self.checksums_path.write_text(
            (
                f"{sqlite_hash}  respaldo/database.sqlite3\n"
                f"{media_hash}  respaldo/media.tar.gz\n"
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _sha256(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
