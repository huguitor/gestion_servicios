import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from django.db import models
from django.db.models.signals import post_save, pre_save
from django.test import TestCase

from backup.legacy.importers.master_base import MasterImportError
from backup.legacy.importers.productos import (
    ProductoImpuestoImporter,
    ProductosImporter,
)
from backup.legacy.importers.servicios import (
    ServicioImpuestoImporter,
    ServiciosImporter,
)
from categorias.models import Categoria
from impuestos.models import Impuesto
from marcas.models import Marca
from productos.models import (
    Producto,
    ProductoImpuesto,
    Servicio,
    ServicioImpuesto,
)
from proveedores.models import Proveedor


IMPORTERS = (
    ProductosImporter,
    ServiciosImporter,
    ProductoImpuestoImporter,
    ServicioImpuestoImporter,
)


def source_names(importer_class):
    return tuple(
        name for name in importer_class.columns
        if name not in importer_class.defaults
    ) + importer_class.source_only_columns


def valid_row(importer_class, pk=1):
    row = {}
    for name in source_names(importer_class):
        if name == "id":
            value = pk
        elif name == "creado":
            value = "2020-01-02 03:04:05+00:00"
        elif name == "actualizado":
            value = "2021-06-07 08:09:10+00:00"
        elif name in importer_class.foreign_keys:
            value = 1
        elif name in importer_class.boolean_fields:
            value = 1
        elif name in importer_class.integer_fields:
            value = 10
        elif name in importer_class.decimal_fields:
            value = "123.45"
        elif name in {"foto", "plano"}:
            value = f"legacy/{name}-{pk}.jpg"
        else:
            model_name = name[:-3] if name.endswith("_id") else name
            field = importer_class.model._meta.get_field(model_name)
            if field.choices:
                value = field.choices[0][0]
            elif name in {"imagen", "adjunto"}:
                value = f"servicios/{name}-{pk}.jpg"
            elif name == "sku":
                value = f"SKU-{pk}"
            elif name == "codigo_barras":
                value = f"BAR-{pk}"
            elif name == "codigo_interno":
                value = f"SRV-{pk}"
            elif name == "slug":
                value = f"slug-{pk}"
            elif name == "nombre":
                value = f"Nombre {pk}"
            elif field.null:
                value = None
            else:
                value = ""
        row[name] = value
    return row


def create_source(path, importer_class, rows, *, primary_key=True):
    connection = sqlite3.connect(path)
    for related_model in set(importer_class.foreign_keys.values()):
        connection.execute(
            f'CREATE TABLE "{related_model._meta.db_table}" '
            f'("id" INTEGER PRIMARY KEY)'
        )
    definitions = []
    for name in source_names(importer_class):
        suffix = " PRIMARY KEY" if name == "id" and primary_key else ""
        if name in importer_class.foreign_keys:
            target = importer_class.foreign_keys[name]._meta.db_table
            definitions.append(
                f'"{name}" INTEGER REFERENCES "{target}"("id")'
            )
        else:
            sqlite_type = (
                "INTEGER"
                if name == "id"
                or name in importer_class.integer_fields
                or name in importer_class.boolean_fields
                else "TEXT"
            )
            definitions.append(f'"{name}" {sqlite_type}{suffix}')
    connection.execute(
        f'CREATE TABLE "{importer_class.table_name}" '
        f'({", ".join(definitions)})'
    )
    for row in rows:
        names = tuple(row)
        columns = ", ".join(f'"{name}"' for name in names)
        placeholders = ", ".join("?" for _ in names)
        connection.execute(
            f'INSERT INTO "{importer_class.table_name}" '
            f'({columns}) VALUES ({placeholders})',
            tuple(row[name] for name in names),
        )
    connection.commit()
    connection.close()


class ProductosServiciosImportersTests(TestCase):
    def source_path(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / "database.sqlite3"

    def create_catalogs(self):
        Categoria.objects.bulk_create([Categoria(id=1, nombre="Categoría")])
        Marca.objects.bulk_create([Marca(id=1, nombre="Marca")])
        Proveedor.objects.bulk_create(
            [
                Proveedor(
                    id=1,
                    tipo="juridica",
                    nombre="Proveedor",
                    documento="30123456789",
                    condicion_iva="ri",
                )
            ]
        )

    def create_tax_dependencies(self):
        Impuesto.objects.bulk_create(
            [
                Impuesto(
                    id=1,
                    nombre="IVA",
                    porcentaje="21.00",
                    tipo="ambos",
                )
            ]
        )
        Producto.objects.bulk_create(
            [
                Producto(
                    id=1,
                    sku="P-1",
                    nombre="Producto",
                    precio_venta="10.00",
                    stock=1,
                )
            ]
        )
        Servicio.objects.bulk_create(
            [
                Servicio(
                    id=1,
                    codigo_interno="S-1",
                    nombre="Servicio",
                    costo_base="1.00",
                    precio_base="2.00",
                )
            ]
        )

    def test_imports_product_with_defaults_decimals_timestamps_and_references(self):
        self.create_catalogs()
        path = self.source_path()
        row = valid_row(ProductosImporter, 9)
        create_source(path, ProductosImporter, [row])

        report = ProductosImporter(path).import_all()

        producto = Producto.objects.get(pk=9)
        self.assertEqual(str(producto.precio_venta), "123.45")
        self.assertEqual(str(producto.costo_compra), "123.45")
        self.assertEqual(producto.stock_reservado, 0)
        self.assertEqual(
            producto.creado,
            datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(
            producto.actualizado,
            datetime(2021, 6, 7, 8, 9, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(report.imported_count, 1)
        self.assertEqual(report.defaults_applied["stock_reservado"]["value"], 0)
        self.assertEqual(
            {(item["source_field"], item["path"]) for item in report.preserved_references},
            {("foto", "legacy/foto-9.jpg"), ("plano", "legacy/plano-9.jpg")},
        )

    def test_imports_service_with_video_default_and_file_references(self):
        self.create_catalogs()
        path = self.source_path()
        row = valid_row(ServiciosImporter, 8)
        create_source(path, ServiciosImporter, [row])

        report = ServiciosImporter(path).import_all()

        servicio = Servicio.objects.get(pk=8)
        self.assertEqual(str(servicio.costo_base), "123.45")
        self.assertEqual(str(servicio.precio_base), "123.45")
        self.assertFalse(servicio.video)
        self.assertEqual(servicio.imagen.name, "servicios/imagen-8.jpg")
        self.assertEqual(servicio.adjunto.name, "servicios/adjunto-8.jpg")
        self.assertEqual(report.defaults_applied["video"]["value"], None)

    def test_imports_tax_relations_with_historical_primary_keys(self):
        self.create_tax_dependencies()
        for importer_class, target_model in (
            (ProductoImpuestoImporter, ProductoImpuesto),
            (ServicioImpuestoImporter, ServicioImpuesto),
        ):
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                create_source(path, importer_class, [valid_row(importer_class, 17)])

                report = importer_class(path).import_all()

                relation = target_model._default_manager.get()
                self.assertEqual(relation.pk, 17)
                self.assertEqual(relation.impuesto_id, 1)
                self.assertEqual(report.imported_count, 1)
                target_model._default_manager.all().delete()

    def test_empty_sources(self):
        self.create_catalogs()
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                if importer_class in (
                    ProductoImpuestoImporter,
                    ServicioImpuestoImporter,
                ):
                    self.create_tax_dependencies()
                path = self.source_path()
                create_source(path, importer_class, [])
                report = importer_class(path).import_all()
                self.assertEqual(report.imported_count, 0)
                ProductoImpuesto.objects.all().delete()
                ServicioImpuesto.objects.all().delete()
                Producto.objects.all().delete()
                Servicio.objects.all().delete()
                Impuesto.objects.all().delete()

    def test_invalid_foreign_keys_abort(self):
        self.create_catalogs()
        self.create_tax_dependencies()
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                row = valid_row(importer_class)
                first_fk = next(iter(importer_class.foreign_keys))
                row[first_fk] = 999
                create_source(path, importer_class, [row])

                with self.assertRaisesRegex(MasterImportError, "FK inválidas"):
                    importer_class(path).import_all()

    def test_duplicate_tax_relations_abort(self):
        self.create_tax_dependencies()
        for importer_class in (
            ProductoImpuestoImporter,
            ServicioImpuestoImporter,
        ):
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                first = valid_row(importer_class, 1)
                second = valid_row(importer_class, 2)
                create_source(path, importer_class, [first, second])

                with self.assertRaisesRegex(
                    MasterImportError, "Conflictos de unicidad"
                ):
                    importer_class(path).import_all()

    def test_destination_must_be_empty(self):
        self.create_catalogs()
        Producto.objects.bulk_create(
            [Producto(id=1, nombre="Existente", precio_venta="1.00", stock=0)]
        )
        path = self.source_path()
        create_source(path, ProductosImporter, [valid_row(ProductosImporter, 2)])

        with self.assertRaisesRegex(MasterImportError, "no está vacío"):
            ProductosImporter(path).import_all()

    def test_bulk_import_does_not_emit_save_signals(self):
        self.create_catalogs()
        for importer_class in IMPORTERS:
            with self.subTest(importer=importer_class.__name__):
                if importer_class in (
                    ProductoImpuestoImporter,
                    ServicioImpuestoImporter,
                ):
                    self.create_tax_dependencies()
                path = self.source_path()
                create_source(path, importer_class, [valid_row(importer_class)])
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
                ProductoImpuesto.objects.all().delete()
                ServicioImpuesto.objects.all().delete()
                Producto.objects.all().delete()
                Servicio.objects.all().delete()
                Impuesto.objects.all().delete()

    def test_rolls_back_first_batch_when_later_row_is_invalid(self):
        self.create_catalogs()
        for importer_class in (ProductosImporter, ServiciosImporter):
            with self.subTest(importer=importer_class.__name__):
                path = self.source_path()
                first = valid_row(importer_class, 1)
                second = valid_row(importer_class, 2)
                second["actualizado"] = "fecha-inválida"
                create_source(path, importer_class, [first, second])

                with self.assertRaisesRegex(MasterImportError, "actualizado"):
                    importer_class(path, batch_size=1).import_all()

                self.assertFalse(importer_class.model._default_manager.exists())

    def test_duplicate_primary_key_and_unique_field_abort(self):
        self.create_catalogs()
        path = self.source_path()
        first = valid_row(ProductosImporter, 1)
        second = valid_row(ProductosImporter, 1)
        second["sku"] = "OTRO"
        second["codigo_barras"] = "OTRO"
        second["nombre"] = "Otro"
        second["slug"] = "otro"
        create_source(path, ProductosImporter, [first, second], primary_key=False)
        with self.assertRaisesRegex(MasterImportError, "PK duplicadas"):
            ProductosImporter(path).import_all()

        path = self.source_path()
        first = valid_row(ServiciosImporter, 1)
        second = valid_row(ServiciosImporter, 2)
        second["codigo_interno"] = first["codigo_interno"]
        create_source(path, ServiciosImporter, [first, second])
        with self.assertRaisesRegex(MasterImportError, "Conflictos de unicidad"):
            ServiciosImporter(path).import_all()
