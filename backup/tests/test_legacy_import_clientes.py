import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from django.db.models.signals import post_save, pre_save
from django.test import TestCase

from backup.legacy.importers.clientes import (
    ClienteImportError,
    ClientesImporter,
)
from clientes.models import Cliente


CLIENTE_COLUMNS = """
    id INTEGER PRIMARY KEY,
    tipo VARCHAR(10) NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    apellido VARCHAR(200) NULL,
    documento VARCHAR(20) NULL UNIQUE,
    condicion_iva VARCHAR(20) NOT NULL,
    telefono VARCHAR(30) NULL,
    email VARCHAR(254) NULL,
    direccion VARCHAR(255) NULL,
    ciudad VARCHAR(100) NULL,
    provincia VARCHAR(100) NULL,
    pais VARCHAR(100) NOT NULL,
    activo BOOL NOT NULL,
    creado DATETIME NOT NULL,
    actualizado DATETIME NOT NULL
"""


def legacy_cliente(pk=7, **overrides):
    values = {
        "id": pk,
        "tipo": "fisica",
        "nombre": f"Cliente {pk}",
        "apellido": "Histórico",
        "documento": f"{20_000_000 + pk:08d}",
        "condicion_iva": "cf",
        "telefono": "011-0000-0000",
        "email": f"cliente-{pk}@example.invalid",
        "direccion": "Calle histórica",
        "ciudad": "Ciudad",
        "provincia": "Provincia",
        "pais": "Argentina",
        "activo": 1,
        "creado": "2020-01-02 03:04:05+00:00",
        "actualizado": "2021-06-07 08:09:10+00:00",
    }
    values.update(overrides)
    return values


def create_legacy_database(
    path: Path,
    rows=(),
    *,
    columns=CLIENTE_COLUMNS,
    setup_sql=(),
):
    connection = sqlite3.connect(path)
    for statement in setup_sql:
        connection.execute(statement)
    connection.execute(f"CREATE TABLE clientes_cliente ({columns})")
    for row in rows:
        names = tuple(row)
        placeholders = ", ".join("?" for _ in names)
        connection.execute(
            f"INSERT INTO clientes_cliente ({', '.join(names)}) "
            f"VALUES ({placeholders})",
            tuple(row[name] for name in names),
        )
    connection.commit()
    connection.close()


class ClientesImporterTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_path = Path(self.temporary.name) / "database.sqlite3"

    def test_imports_clients_and_reports_statistics(self):
        create_legacy_database(
            self.database_path,
            [legacy_cliente(7), legacy_cliente(12, tipo="juridica")],
        )

        report = ClientesImporter(
            self.database_path,
            batch_size=1,
        ).import_all()

        self.assertEqual(Cliente.objects.count(), 2)
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.read_count, 2)
        self.assertEqual(report.imported_count, 2)
        self.assertEqual(report.skipped_count, 0)
        self.assertEqual(report.batch_count, 2)
        self.assertEqual((report.min_pk, report.max_pk), (7, 12))
        self.assertEqual(report.warnings, [])

    def test_empty_source_imports_no_clients(self):
        create_legacy_database(self.database_path)

        report = ClientesImporter(self.database_path).import_all()

        self.assertEqual(report.read_count, 0)
        self.assertEqual(report.imported_count, 0)
        self.assertFalse(Cliente.objects.exists())

    def test_preserves_primary_key_and_historical_fields(self):
        source = legacy_cliente(
            41,
            tipo="juridica",
            nombre="Razón histórica",
            apellido="",
            condicion_iva="ri",
            telefono="",
            email="contacto@example.invalid",
            direccion="Dirección anterior",
            ciudad="Localidad",
            provincia="Buenos Aires",
            pais="Uruguay",
            activo=0,
        )
        create_legacy_database(self.database_path, [source])

        ClientesImporter(self.database_path).import_all()

        cliente = Cliente.objects.get()
        self.assertEqual(cliente.pk, 41)
        for field_name in (
            "tipo",
            "nombre",
            "apellido",
            "documento",
            "condicion_iva",
            "telefono",
            "email",
            "direccion",
            "ciudad",
            "provincia",
            "pais",
        ):
            self.assertEqual(getattr(cliente, field_name), source[field_name])
        self.assertFalse(cliente.activo)
        self.assertEqual(
            cliente.creado,
            datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(
            cliente.actualizado,
            datetime(2021, 6, 7, 8, 9, 10, tzinfo=timezone.utc),
        )

    def test_applies_default_payment_term(self):
        create_legacy_database(self.database_path, [legacy_cliente()])

        report = ClientesImporter(self.database_path).import_all()

        self.assertEqual(Cliente.objects.get().plazo_cobro_dias, 0)
        self.assertEqual(
            report.defaults_applied["plazo_cobro_dias"],
            {"value": 0, "applied_count": 1},
        )

    def test_preserves_null_and_empty_values(self):
        source = legacy_cliente(
            documento=None,
            telefono=None,
            email="",
            direccion=None,
            ciudad="",
            provincia=None,
        )
        create_legacy_database(self.database_path, [source])

        ClientesImporter(self.database_path).import_all()

        cliente = Cliente.objects.get()
        self.assertIsNone(cliente.documento)
        self.assertIsNone(cliente.telefono)
        self.assertEqual(cliente.email, "")
        self.assertIsNone(cliente.direccion)
        self.assertEqual(cliente.ciudad, "")
        self.assertIsNone(cliente.provincia)

    def test_unexpected_foreign_key_aborts(self):
        columns = CLIENTE_COLUMNS + (
            ", parent_id INTEGER NULL REFERENCES parent_table(id)"
        )
        create_legacy_database(
            self.database_path,
            columns=columns,
            setup_sql=("CREATE TABLE parent_table (id INTEGER PRIMARY KEY)",),
        )

        with self.assertRaisesRegex(ClienteImportError, "FK no contempladas"):
            ClientesImporter(self.database_path).import_all()

    def test_duplicate_primary_key_aborts(self):
        columns = CLIENTE_COLUMNS.replace("id INTEGER PRIMARY KEY", "id INTEGER")
        first = legacy_cliente(5)
        second = legacy_cliente(5, documento="30000005")
        create_legacy_database(
            self.database_path,
            [first, second],
            columns=columns,
        )

        with self.assertRaisesRegex(ClienteImportError, "PK duplicadas"):
            ClientesImporter(self.database_path).import_all()

        self.assertFalse(Cliente.objects.exists())

    def test_null_primary_key_aborts(self):
        columns = CLIENTE_COLUMNS.replace("id INTEGER PRIMARY KEY", "id INTEGER")
        source = legacy_cliente(1, documento="30123456789")
        source["id"] = None
        create_legacy_database(
            self.database_path,
            [source],
            columns=columns,
        )

        with self.assertRaisesRegex(ClienteImportError, "PK nulas"):
            ClientesImporter(self.database_path).import_all()

        self.assertFalse(Cliente.objects.exists())

    def test_duplicate_unique_document_aborts(self):
        columns = CLIENTE_COLUMNS.replace(
            "documento VARCHAR(20) NULL UNIQUE",
            "documento VARCHAR(20) NULL",
        )
        first = legacy_cliente(1, documento="30111222")
        second = legacy_cliente(2, documento="30111222")
        create_legacy_database(
            self.database_path,
            [first, second],
            columns=columns,
        )

        with self.assertRaisesRegex(ClienteImportError, "campo único documento"):
            ClientesImporter(self.database_path).import_all()

        self.assertFalse(Cliente.objects.exists())

    def test_bulk_operations_do_not_emit_save_signals(self):
        create_legacy_database(self.database_path, [legacy_cliente()])
        pre_receiver = Mock()
        post_receiver = Mock()
        pre_save.connect(pre_receiver, sender=Cliente)
        post_save.connect(post_receiver, sender=Cliente)
        self.addCleanup(pre_save.disconnect, pre_receiver, sender=Cliente)
        self.addCleanup(post_save.disconnect, post_receiver, sender=Cliente)

        ClientesImporter(self.database_path).import_all()

        pre_receiver.assert_not_called()
        post_receiver.assert_not_called()

    def test_rolls_back_first_batch_when_later_batch_is_invalid(self):
        create_legacy_database(
            self.database_path,
            [
                legacy_cliente(1),
                legacy_cliente(2, email="email-inválido"),
            ],
        )

        with self.assertRaisesRegex(ClienteImportError, "validaciones"):
            ClientesImporter(
                self.database_path,
                batch_size=1,
            ).import_all()

        self.assertFalse(Cliente.objects.exists())

    def test_non_empty_destination_aborts(self):
        Cliente.objects.create(
            tipo="juridica",
            nombre="Existente",
            documento="30999888777",
            condicion_iva="ri",
        )
        create_legacy_database(self.database_path, [legacy_cliente()])

        with self.assertRaisesRegex(ClienteImportError, "no está vacía"):
            ClientesImporter(self.database_path).import_all()

        self.assertEqual(Cliente.objects.count(), 1)
