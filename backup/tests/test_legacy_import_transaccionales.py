import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.test import TestCase

from backup.legacy.importers.master_base import MasterImportError
from backup.legacy.importers.pedidos import (
    PedidoImporter,
    PedidoItemImporter,
    PedidosImporter,
)
from backup.legacy.importers.presupuestos import (
    PresupuestoAdjuntoImporter,
    PresupuestoImporter,
    PresupuestoItemImporter,
    PresupuestosImporter,
)
from backup.legacy.importers.remitos import (
    ItemRemitoImporter,
    RemitoAdjuntoImporter,
    RemitoImporter,
    RemitosImporter,
)
from clientes.models import Cliente
from comprobantes.models import Comprobante
from pedidos.models import Pedido, PedidoItem
from presupuestos.models import Presupuesto, PresupuestoAdjunto, PresupuestoItem
from productos.models import Producto, Servicio
from remitos.models import ItemRemito, Remito, RemitoAdjunto


User = get_user_model()

PRESUPUESTO_IMPORTERS = (
    PresupuestoImporter,
    PresupuestoItemImporter,
    PresupuestoAdjuntoImporter,
)
REMITO_IMPORTERS = (RemitoImporter, ItemRemitoImporter, RemitoAdjuntoImporter)
PEDIDO_IMPORTERS = (PedidoImporter, PedidoItemImporter)


def source_columns(importer_class):
    return tuple(
        name for name in importer_class.columns
        if name not in importer_class.defaults
    ) + importer_class.source_only_columns


def create_domain_source(path, importer_classes, rows_by_table):
    connection = sqlite3.connect(path)
    domain_tables = {item.table_name for item in importer_classes}
    related_tables = {
        model._meta.db_table
        for importer in importer_classes
        for model in importer.foreign_keys.values()
    }
    for table in sorted(related_tables - domain_tables):
        connection.execute(f'CREATE TABLE "{table}" ("id" INTEGER PRIMARY KEY)')
    for importer in importer_classes:
        definitions = []
        for name in source_columns(importer):
            if name in importer.foreign_keys:
                target = importer.foreign_keys[name]._meta.db_table
                definition = (
                    f'"{name}" INTEGER REFERENCES "{target}"("id")'
                )
            else:
                sql_type = (
                    "INTEGER"
                    if name == "id"
                    or name in importer.integer_fields
                    or name in importer.boolean_fields
                    else "TEXT"
                )
                definition = f'"{name}" {sql_type}'
            if name == "id":
                definition += " PRIMARY KEY"
            definitions.append(definition)
        connection.execute(
            f'CREATE TABLE "{importer.table_name}" '
            f'({", ".join(definitions)})'
        )
        for row in rows_by_table.get(importer.table_name, []):
            names = tuple(row)
            columns = ", ".join(f'"{name}"' for name in names)
            placeholders = ", ".join("?" for _ in names)
            connection.execute(
                f'INSERT INTO "{importer.table_name}" '
                f'({columns}) VALUES ({placeholders})',
                tuple(row[name] for name in names),
            )
    connection.commit()
    connection.close()


def presupuesto_rows(*, wrong_totals=False, invalid_item_fk=False):
    subtotal = "999.00" if wrong_totals else "20.00"
    return {
        "presupuestos_presupuesto": [
            {
                "id": 10, "fecha": "2020-01-02 03:04:05+00:00",
                "valido_hasta": None, "observaciones": "",
                "estado": "enviado", "creado": "2020-01-02 03:04:05+00:00",
                "actualizado": "2021-01-02 03:04:05+00:00",
                "cliente_id": 1, "creado_por_id": 1, "comprobante_id": 1,
                "condiciones_comerciales": None, "iva_porcentaje": "21.00",
                "iva_valor": "4.20", "subtotal": subtotal,
                "total": "24.20", "numero": 77, "anulado_por_id": None,
                "fecha_anulacion": None, "motivo_anulacion": "",
            }
        ],
        "presupuestos_presupuestoitem": [
            {
                "id": 20, "descripcion": "Detalle histórico", "cantidad": 2,
                "precio_unitario": "10.00", "presupuesto_id": 10,
                "producto_id": 999 if invalid_item_fk else 1,
                "servicio_id": None, "codigo": "P-1",
            }
        ],
        "presupuestos_presupuestoadjunto": [
            {
                "id": 30, "archivo": "presupuestos/legacy.pdf",
                "tipo": "plano", "nombre_original": "legacy.pdf",
                "descripcion": "", "tamaño": 100, "extension": "pdf",
                "fecha_subida": "2020-02-03 04:05:06+00:00",
                "fecha_modificacion": "2021-02-03 04:05:06+00:00",
                "es_publico": 1, "version": 1, "checksum": "",
                "metadata": '{"origen":"legacy"}', "presupuesto_id": 10,
                "subido_por_id": None,
            }
        ],
    }


def remito_rows(*, invalid_child=False):
    items = [
        {
            "id": 21, "cantidad": "1.50", "unidad_medida": "UNIDAD",
            "codigo": "", "observaciones": "", "orden": 0,
            "remito_id": 11, "descripcion": "Entrega histórica",
        }
    ]
    if invalid_child:
        items.append(
            {
                "id": 22, "cantidad": "-1.50", "unidad_medida": "UNIDAD",
                "codigo": "", "observaciones": "", "orden": 1,
                "remito_id": 11, "descripcion": "Detalle inválido",
            }
        )
    return {
        "remitos_remito": [
            {
                "id": 11, "numero": 88, "fecha_emision": "2020-03-04",
                "fecha_entrega": None, "origen": "", "destino": "Destino",
                "presupuesto_relacionado": "PRES-77",
                "numero_referencia": "", "estado": "pendiente",
                "creado_por_id": 1,
                "actualizado": "2021-03-04 05:06:07+00:00",
                "creado": "2020-03-04 05:06:07+00:00",
                "observaciones": "", "anulado_por_id": None,
                "comprobante_id": 2, "fecha_anulacion": None,
                "licitacion_orden": "", "motivo_anulacion": "",
                "cliente_id": 1,
            }
        ],
        "remitos_itemremito": items,
        "remitos_remitoadjunto": [
            {
                "id": 31, "archivo": "remitos/legacy.jpg", "tipo": "foto",
                "nombre_original": "", "descripcion": "", "extension": "jpg",
                "fecha_subida": "2020-03-05 05:06:07+00:00",
                "fecha_modificacion": "2021-03-05 05:06:07+00:00",
                "remito_id": 11, "subido_por_id": None, "tamaño": 50,
            }
        ],
    }


def pedido_rows(*, wrong_totals=False, invalid_child=False):
    return {
        "pedidos_pedido": [
            {
                "id": 12, "estado": "confirmado",
                "observaciones_cliente": "", "observaciones_internas": "",
                "subtotal": "999.00" if wrong_totals else "20.00",
                "total": "20.00", "activo": 1,
                "creado": "2020-04-05 06:07:08+00:00",
                "actualizado": "2021-04-05 06:07:08+00:00",
                "cliente_id": 1, "cliente_web_id": None,
            }
        ],
        "pedidos_pedidoitem": [
            {
                "id": 22, "tipo_item": "mercaderia",
                "nombre_snapshot": "Producto histórico",
                "codigo_snapshot": "P-1", "precio_unitario_snapshot": "10.00",
                "cantidad": 2, "subtotal": "20.00", "pedido_id": 12,
                "producto_id": None if invalid_child else 1,
                "servicio_id": None,
            }
        ],
    }


class TransactionalImportersTests(TestCase):
    def setUp(self):
        User.objects.bulk_create(
            [
                User(
                    id=1, username="legacy", password="hash",
                    date_joined="2020-01-01T00:00:00Z",
                )
            ]
        )
        Cliente.objects.bulk_create(
            [
                Cliente(
                    id=1, tipo="juridica", nombre="Cliente",
                    documento="30123456789", condicion_iva="ri",
                )
            ]
        )
        Comprobante.objects.bulk_create(
            [
                Comprobante(
                    id=1, tipo="PRES", serie="00001",
                    numero_inicial=1, proximo_numero=100, numero_final=999,
                ),
                Comprobante(
                    id=2, tipo="REMI", serie="00001",
                    numero_inicial=1, proximo_numero=100, numero_final=999,
                ),
            ]
        )
        Producto.objects.bulk_create(
            [Producto(id=1, sku="P-1", nombre="Producto", precio_venta=10, stock=5)]
        )
        Servicio.objects.bulk_create(
            [Servicio(id=1, codigo_interno="S-1", nombre="Servicio")]
        )

    def source_path(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / "database.sqlite3"

    def test_imports_complete_presupuesto_domain_and_preserves_history(self):
        path = self.source_path()
        create_domain_source(path, PRESUPUESTO_IMPORTERS, presupuesto_rows())

        reports = PresupuestosImporter(path, batch_size=1).import_all()

        presupuesto = Presupuesto.objects.get(pk=10)
        self.assertEqual(presupuesto.numero, 77)
        self.assertEqual(str(presupuesto.total), "24.20")
        self.assertEqual(PresupuestoItem.objects.get(pk=20).cantidad, 2)
        self.assertEqual(PresupuestoAdjunto.objects.get(pk=30).metadata["origen"], "legacy")
        self.assertEqual(
            reports["adjuntos"].preserved_references[0]["path"],
            "presupuestos/legacy.pdf",
        )
        self.assertEqual(reports["presupuestos"].warnings, [])

    def test_preserves_totals_and_warns_when_current_calculation_differs(self):
        path = self.source_path()
        create_domain_source(
            path, PRESUPUESTO_IMPORTERS, presupuesto_rows(wrong_totals=True)
        )

        reports = PresupuestosImporter(path).import_all()

        self.assertEqual(str(Presupuesto.objects.get().subtotal), "999.00")
        self.assertEqual(
            reports["presupuestos"].warnings[0]["code"],
            "historical_total_difference",
        )

    def test_imports_complete_remito_domain_and_preserves_references(self):
        path = self.source_path()
        create_domain_source(path, REMITO_IMPORTERS, remito_rows())

        reports = RemitosImporter(path).import_all()

        remito = Remito.objects.get(pk=11)
        self.assertEqual(remito.presupuesto_relacionado, "PRES-77")
        self.assertEqual(str(ItemRemito.objects.get(pk=21).cantidad), "1.50")
        self.assertEqual(
            reports["adjuntos"].preserved_references[0]["path"],
            "remitos/legacy.jpg",
        )

    def test_imports_complete_pedido_without_stock_movements(self):
        path = self.source_path()
        create_domain_source(path, PEDIDO_IMPORTERS, pedido_rows())

        reports = PedidosImporter(path).import_all()

        pedido = Pedido.objects.get(pk=12)
        self.assertEqual(pedido.estado, "confirmado")
        self.assertFalse(pedido.stock_reservado_aplicado)
        self.assertFalse(pedido.stock_finalizado_aplicado)
        self.assertEqual(PedidoItem.objects.get(pk=22).producto_id, 1)
        self.assertEqual(reports["pedidos"].warnings, [])

    def test_pedido_preserves_historical_total_and_warns_on_difference(self):
        path = self.source_path()
        create_domain_source(
            path, PEDIDO_IMPORTERS, pedido_rows(wrong_totals=True)
        )

        reports = PedidosImporter(path).import_all()

        self.assertEqual(str(Pedido.objects.get().subtotal), "999.00")
        self.assertEqual(
            reports["pedidos"].warnings[0]["code"],
            "historical_total_difference",
        )

    def test_empty_origins(self):
        for coordinator, importers in (
            (PresupuestosImporter, PRESUPUESTO_IMPORTERS),
            (RemitosImporter, REMITO_IMPORTERS),
            (PedidosImporter, PEDIDO_IMPORTERS),
        ):
            with self.subTest(domain=coordinator.__name__):
                path = self.source_path()
                create_domain_source(path, importers, {})
                reports = coordinator(path).import_all()
                self.assertTrue(all(report.imported_count == 0 for report in reports.values()))

    def test_invalid_child_fk_rolls_back_complete_domain(self):
        path = self.source_path()
        create_domain_source(
            path,
            PRESUPUESTO_IMPORTERS,
            presupuesto_rows(invalid_item_fk=True),
        )
        with self.assertRaisesRegex(MasterImportError, "FK inválidas"):
            PresupuestosImporter(path).import_all()
        self.assertFalse(Presupuesto.objects.exists())

    def test_invalid_later_child_rolls_back_complete_domain(self):
        path = self.source_path()
        create_domain_source(
            path, REMITO_IMPORTERS, remito_rows(invalid_child=True)
        )
        with self.assertRaisesRegex(MasterImportError, "cantidad"):
            RemitosImporter(path, batch_size=1).import_all()
        self.assertFalse(Remito.objects.exists())

    def test_invalid_choice_and_xor_abort_pedido(self):
        rows = pedido_rows(invalid_child=True)
        rows["pedidos_pedido"][0]["estado"] = "estado-inválido"
        path = self.source_path()
        create_domain_source(path, PEDIDO_IMPORTERS, rows)
        with self.assertRaises(MasterImportError):
            PedidosImporter(path).import_all()
        self.assertFalse(Pedido.objects.exists())

    def test_destination_not_empty_aborts(self):
        Presupuesto.objects.bulk_create(
            [
                Presupuesto(
                    id=10, cliente_id=1, creado_por_id=1,
                    comprobante_id=1,
                )
            ]
        )
        path = self.source_path()
        create_domain_source(path, PRESUPUESTO_IMPORTERS, presupuesto_rows())
        with self.assertRaisesRegex(MasterImportError, "no está vacío"):
            PresupuestosImporter(path).import_all()

    def test_no_save_signals_are_emitted(self):
        path = self.source_path()
        create_domain_source(path, PRESUPUESTO_IMPORTERS, presupuesto_rows())
        receivers = []
        for model in (Presupuesto, PresupuestoItem, PresupuestoAdjunto):
            pre_receiver, post_receiver = Mock(), Mock()
            pre_save.connect(pre_receiver, sender=model)
            post_save.connect(post_receiver, sender=model)
            receivers.append((model, pre_receiver, post_receiver))
        try:
            PresupuestosImporter(path).import_all()
        finally:
            for model, pre_receiver, post_receiver in receivers:
                pre_save.disconnect(pre_receiver, sender=model)
                post_save.disconnect(post_receiver, sender=model)
        for _, pre_receiver, post_receiver in receivers:
            pre_receiver.assert_not_called()
            post_receiver.assert_not_called()
