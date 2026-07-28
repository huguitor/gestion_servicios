import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from django.db import models
from django.db.models.signals import post_save, pre_save
from django.test import TestCase

from backup.legacy.importers.categorias import CategoriasImporter
from backup.legacy.importers.configuracion import ConfiguracionImporter
from backup.legacy.importers.impuestos import ImpuestosImporter
from backup.legacy.importers.marcas import MarcasImporter
from backup.legacy.importers.master_base import MasterImportError
from backup.legacy.importers.proveedores import ProveedoresImporter


IMPORTERS = (
    ConfiguracionImporter,
    ImpuestosImporter,
    CategoriasImporter,
    MarcasImporter,
    ProveedoresImporter,
)


def valid_row(importer_class, pk):
    row = {}
    model = importer_class.model
    for name in importer_class.columns:
        field = model._meta.get_field(name)
        if name == "id":
            value = pk
        elif name == "creado":
            value = "2020-01-02 03:04:05+00:00"
        elif name == "actualizado":
            value = "2021-06-07 08:09:10+00:00"
        elif field.null:
            value = None
        elif isinstance(field, models.BooleanField):
            value = 1
        elif isinstance(field, models.DecimalField):
            value = "21.00"
        elif isinstance(field, models.IntegerField):
            value = 10
        elif field.choices:
            value = field.choices[0][0]
        elif name == "nombre":
            value = f"Nombre {pk}"
        elif isinstance(field, (models.CharField, models.TextField)) and not field.blank:
            value = f"Valor {pk}"
        else:
            value = ""
        row[name] = value
    if importer_class is ConfiguracionImporter:
        row["activo"] = 1 if pk == 1 else 0
        row["nombre_empresa"] = f"Empresa {pk}"
        row["nombre_fantasia"] = f"Fantasía {pk}"
        row["descripcion_sistema"] = f"Sistema {pk}"
    if importer_class is ProveedoresImporter:
        row["nombre"] = f"Proveedor {pk}"
        row["documento"] = str(30_000_000_000 + pk)
    return row


def create_source(path, importer_class, rows, *, primary_key=True, foreign_key=False):
    definitions = []
    for name in importer_class.columns:
        suffix = " PRIMARY KEY" if name == "id" and primary_key else ""
        sqlite_type = (
            "INTEGER"
            if name == "id"
            or name in importer_class.boolean_fields
            or name in importer_class.integer_fields
            else "TEXT"
        )
        definitions.append(f'"{name}" {sqlite_type}{suffix}')
    if foreign_key:
        definitions.append(
            '"parent_id" INTEGER NULL REFERENCES "parent_table"("id")'
        )
    connection = sqlite3.connect(path)
    if foreign_key:
        connection.execute(
            'CREATE TABLE "parent_table" ("id" INTEGER PRIMARY KEY)'
        )
    connection.execute(
        f'CREATE TABLE "{importer_class.table_name}" '
        f'({", ".join(definitions)})'
    )
    for row in rows:
        names = tuple(row)
        placeholders = ", ".join("?" for _ in names)
        quoted = ", ".join(f'"{name}"' for name in names)
        connection.execute(
            f'INSERT INTO "{importer_class.table_name}" '
            f'({quoted}) VALUES ({placeholders})',
            tuple(row[name] for name in names),
        )
    connection.commit()
    connection.close()


class MasterImportersTests(TestCase):
    def source_path(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / "database.sqlite3"

    def test_correct_import_empty_source_pk_nulls_and_timestamps(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                row = valid_row(importer_class, 1)
                create_source(path, importer_class, [row])

                report = importer_class(path).import_all()

                instance = importer_class.model._default_manager.get(pk=1)
                self.assertEqual(report.read_count, 1)
                self.assertEqual(report.imported_count, 1)
                self.assertEqual(report.skipped_count, 0)
                self.assertEqual((report.min_pk, report.max_pk), (1, 1))
                self.assertEqual(
                    instance.creado,
                    datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
                )
                self.assertEqual(
                    instance.actualizado,
                    datetime(2021, 6, 7, 8, 9, 10, tzinfo=timezone.utc),
                )
                for name in importer_class.nullable_fields:
                    if row[name] is not None:
                        continue
                    value = getattr(instance, name)
                    if isinstance(
                        importer_class.model._meta.get_field(name),
                        models.FileField,
                    ):
                        self.assertFalse(value)
                    else:
                        self.assertIsNone(value)
                importer_class.model._default_manager.all().delete()

    def test_empty_source(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                create_source(path, importer_class, [])

                report = importer_class(path).import_all()

                self.assertEqual(report.imported_count, 0)
                self.assertFalse(
                    importer_class.model._default_manager.exists()
                )

    def test_unique_conflicts_abort(self):
        for importer_class in IMPORTERS:
            if not importer_class.unique_fields:
                continue
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                first = valid_row(importer_class, 1)
                second = valid_row(importer_class, 2)
                field_name = importer_class.unique_fields[0]
                second[field_name] = first[field_name]
                create_source(path, importer_class, [first, second])

                with self.assertRaisesRegex(
                    MasterImportError, "Conflictos de unicidad"
                ):
                    importer_class(path).import_all()

    def test_unexpected_foreign_keys_abort(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                create_source(
                    path,
                    importer_class,
                    [],
                    foreign_key=True,
                )

                with self.assertRaisesRegex(
                    MasterImportError, "FK no contempladas"
                ):
                    importer_class(path).import_all()

    def test_duplicate_primary_keys_abort(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                first = valid_row(importer_class, 1)
                second = valid_row(importer_class, 1)
                if importer_class is ConfiguracionImporter:
                    second["activo"] = 0
                for unique in importer_class.unique_fields:
                    second[unique] = f"Otro-{unique}"
                create_source(
                    path,
                    importer_class,
                    [first, second],
                    primary_key=False,
                )

                with self.assertRaisesRegex(
                    MasterImportError, "PK duplicadas"
                ):
                    importer_class(path).import_all()

    def test_bulk_operations_do_not_emit_save_signals(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                create_source(
                    path,
                    importer_class,
                    [valid_row(importer_class, 1)],
                )
                pre_receiver = Mock()
                post_receiver = Mock()
                pre_save.connect(pre_receiver, sender=importer_class.model)
                post_save.connect(post_receiver, sender=importer_class.model)
                try:
                    importer_class(path).import_all()
                finally:
                    pre_save.disconnect(pre_receiver, sender=importer_class.model)
                    post_save.disconnect(post_receiver, sender=importer_class.model)

                pre_receiver.assert_not_called()
                post_receiver.assert_not_called()
                importer_class.model._default_manager.all().delete()

    def test_non_empty_destination_aborts(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                row = valid_row(importer_class, 1)
                create_source(path, importer_class, [row])
                importer = importer_class(path)
                importer.prepare()
                importer._validated = True
                instance = importer.build_instance(row)
                importer_class.model._default_manager.bulk_create([instance])

                with self.assertRaisesRegex(
                    MasterImportError, "no está vacío"
                ):
                    importer_class(path).import_all()
                importer_class.model._default_manager.all().delete()

    def test_rolls_back_when_later_batch_is_invalid(self):
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                first = valid_row(importer_class, 1)
                second = valid_row(importer_class, 2)
                second["actualizado"] = "fecha-inválida"
                create_source(path, importer_class, [first, second])

                with self.assertRaisesRegex(
                    MasterImportError, "actualizado"
                ):
                    importer_class(path, batch_size=1).import_all()

                self.assertFalse(
                    importer_class.model._default_manager.exists()
                )
