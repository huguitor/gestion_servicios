import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from backup.legacy.media_reader import sha256_file
from backup.legacy.validators import (
    BusinessTablesEmptyValidator,
    MediaVerifiableValidator,
    MigrationsAppliedValidator,
    PostgreSQLAccessibleValidator,
    PreflightError,
    SQLiteAccessibleValidator,
    StagingAvailableValidator,
    TechnicalTablesValidator,
    ValidationContext,
)
from backup.tests.legacy_fixtures import write_checksums, write_tar


class FakeCursor:
    def __init__(self, non_empty=None):
        self.non_empty = non_empty or set()
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql):
        if sql == "SELECT 1":
            self.result = (1,)
            return
        table = sql.split("FROM", 1)[1].split("LIMIT", 1)[0].strip().strip('"')
        self.result = (1,) if table in self.non_empty else None

    def fetchone(self):
        return self.result


class FakeConnection:
    vendor = "postgresql"

    def __init__(self, tables=None, non_empty=None):
        self.tables = set(tables or [])
        self.non_empty = set(non_empty or [])
        self.closed = False
        self.introspection = SimpleNamespace(table_names=lambda: sorted(self.tables))
        self.ops = SimpleNamespace(quote_name=lambda name: f'"{name}"')

    def ensure_connection(self):
        return None

    def cursor(self):
        return FakeCursor(self.non_empty)

    def close(self):
        self.closed = True


def context(root: Path, connection=None, manifest=None):
    return ValidationContext(
        manifest=manifest or SimpleNamespace(media={"references": [], "hashes": {"files": []}}),
        sqlite_path=root / "database.sqlite3",
        media_tar_path=root / "media.tar.gz",
        checksum_manifest_path=root / "SHA256SUMS.txt",
        staging_root=root / "staging",
        media_root=root / "media-root",
        connection=connection or FakeConnection(),
    )


class LegacyValidatorTests(SimpleTestCase):
    databases = set()

    def test_sqlite_accessible_uses_read_only_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = sqlite3.connect(root / "database.sqlite3")
            db.execute("CREATE TABLE ejemplo (id INTEGER PRIMARY KEY)")
            db.close()
            validation_context = context(root)

            result = SQLiteAccessibleValidator().validate(validation_context)

            self.assertEqual(result.status, "ok")
            self.assertIn("ejemplo", validation_context.sqlite_tables)

    def test_missing_sqlite_aborts(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(PreflightError, "No existe SQLite"):
                SQLiteAccessibleValidator().validate(context(Path(temporary)))

    def test_postgresql_must_be_postgresql_and_accessible(self):
        with tempfile.TemporaryDirectory() as temporary:
            validation_context = context(Path(temporary), FakeConnection())

            result = PostgreSQLAccessibleValidator().validate(validation_context)

            self.assertEqual(result.status, "ok")

    def test_pending_migrations_abort(self):
        migration = SimpleNamespace(app_label="clientes", name="0002_pending")
        executor = SimpleNamespace(
            loader=SimpleNamespace(
                graph=SimpleNamespace(leaf_nodes=lambda: [("clientes", "0002_pending")])
            ),
            migration_plan=lambda targets: [(migration, False)],
        )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(PreflightError, "pendientes"):
                MigrationsAppliedValidator(
                    executor_factory=lambda connection: executor
                ).validate(context(Path(temporary)))

    def test_missing_technical_tables_abort(self):
        with tempfile.TemporaryDirectory() as temporary:
            validation_context = context(
                Path(temporary),
                FakeConnection(tables={"django_migrations"}),
            )
            with self.assertRaisesRegex(PreflightError, "técnicas"):
                TechnicalTablesValidator().validate(validation_context)

    def test_non_empty_business_table_aborts(self):
        with tempfile.TemporaryDirectory() as temporary:
            validation_context = context(
                Path(temporary),
                FakeConnection(tables={"clientes_cliente"}, non_empty={"clientes_cliente"}),
            )
            validation_context.postgres_tables = {"clientes_cliente"}
            with self.assertRaisesRegex(PreflightError, "contiene datos"):
                BusinessTablesEmptyValidator(
                    table_provider=lambda: {"clientes_cliente"}
                ).validate(validation_context)

    def test_staging_must_be_writable_and_outside_media_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = StagingAvailableValidator().validate(context(root))
            self.assertEqual(result.status, "ok")
            self.assertEqual(list((root / "staging").iterdir()), [])

            invalid = context(root)
            invalid.staging_root = invalid.media_root / "staging"
            with self.assertRaises(PreflightError):
                StagingAvailableValidator().validate(invalid)

    def test_media_hashes_and_audited_hashes_are_verified_without_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sqlite_path = root / "database.sqlite3"
            sqlite_path.write_bytes(b"sqlite-fixture")
            media_path = root / "media.tar.gz"
            write_tar(media_path, {"data/media/config/logo.png": b"imagen"})
            write_checksums(root / "SHA256SUMS.txt", sqlite_path, media_path)
            manifest = SimpleNamespace(
                media={
                    "references": [
                        {
                            "table": "configuracion_configuracionglobal",
                            "record_id": 1,
                            "field": "logo_principal",
                            "path": "config/logo.png",
                        }
                    ],
                    "hashes": {
                        "files": [
                            {
                                "basename": "database.sqlite3",
                                "actual_sha256": sha256_file(sqlite_path),
                            },
                            {
                                "basename": "media.tar.gz",
                                "actual_sha256": sha256_file(media_path),
                            },
                        ]
                    },
                }
            )

            result = MediaVerifiableValidator().validate(context(root, manifest=manifest))

            self.assertEqual(result.status, "ok")
            self.assertEqual(result.details["file_count"], 1)

            media_path.write_bytes(b"contenido-alterado")
            with self.assertRaisesRegex(PreflightError, "hashes"):
                MediaVerifiableValidator().validate(context(root, manifest=manifest))
