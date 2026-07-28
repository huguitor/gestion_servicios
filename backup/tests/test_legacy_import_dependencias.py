import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.test import TestCase

from backup.legacy.importers.comprobantes import ComprobanteImporter
from backup.legacy.importers.master_base import MasterImportError
from backup.legacy.importers.web_clientes import ClienteWebImporter
from backup.tests.test_legacy_import_transaccionales import create_domain_source
from clientes.models import Cliente
from comprobantes.models import Comprobante
from web_clientes.models import ClienteWeb


User = get_user_model()


class LegacyDependencyImportersTests(TestCase):
    def setUp(self):
        User.objects.bulk_create(
            [
                User(
                    id=1, username="web", password="hash-conservado",
                    email="web@example.invalid",
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

    def path(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / "database.sqlite3"

    def test_imports_comprobantes_without_recalculating_ranges(self):
        path = self.path()
        rows = {
            "comprobantes_comprobante": [
                {
                    "id": 7, "tipo": "PRES", "serie": "00002",
                    "numero_inicial": 10, "proximo_numero": 55,
                    "numero_final": 500,
                }
            ]
        }
        create_domain_source(path, (ComprobanteImporter,), rows)

        report = ComprobanteImporter(path).import_all()

        comprobante = Comprobante.objects.get(pk=7)
        self.assertEqual(comprobante.tipo, "PRES")
        self.assertEqual(comprobante.serie, "00002")
        self.assertEqual(comprobante.numero_inicial, 10)
        self.assertEqual(comprobante.proximo_numero, 55)
        self.assertEqual(comprobante.numero_final, 500)
        self.assertEqual(report.imported_count, 1)

    def test_imports_cliente_web_with_existing_relations_and_timestamps(self):
        path = self.path()
        rows = {
            "web_clientes_clienteweb": [
                {
                    "id": 8, "telefono": "", "activo": 1,
                    "email_verificado": 1, "acepta_terminos": 1,
                    "fecha_alta": "2020-02-03 04:05:06+00:00",
                    "ultimo_acceso": "2021-02-03 04:05:06+00:00",
                    "cliente_id": 1, "user_id": 1,
                }
            ]
        }
        create_domain_source(path, (ClienteWebImporter,), rows)

        report = ClienteWebImporter(path).import_all()

        cliente_web = ClienteWeb.objects.get(pk=8)
        self.assertEqual(cliente_web.user_id, 1)
        self.assertEqual(cliente_web.cliente_id, 1)
        self.assertEqual(cliente_web.telefono, "")
        self.assertTrue(cliente_web.email_verificado)
        self.assertEqual(
            cliente_web.fecha_alta,
            datetime(2020, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
        )
        self.assertEqual(
            cliente_web.ultimo_acceso,
            datetime(2021, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
        )
        self.assertEqual(report.imported_count, 1)
        self.assertEqual(User.objects.get(pk=1).password, "hash-conservado")

    def test_empty_sources(self):
        for importer in (ComprobanteImporter, ClienteWebImporter):
            with self.subTest(importer=importer.__name__):
                path = self.path()
                create_domain_source(path, (importer,), {})
                self.assertEqual(importer(path).import_all().imported_count, 0)

    def test_unique_conflicts_and_invalid_ranges_abort(self):
        path = self.path()
        rows = {
            "comprobantes_comprobante": [
                {
                    "id": 1, "tipo": "PRES", "serie": "00001",
                    "numero_inicial": 1, "proximo_numero": 10,
                    "numero_final": 100,
                },
                {
                    "id": 2, "tipo": "PRES", "serie": "00001",
                    "numero_inicial": 1, "proximo_numero": 20,
                    "numero_final": 100,
                },
            ]
        }
        create_domain_source(path, (ComprobanteImporter,), rows)
        with self.assertRaisesRegex(MasterImportError, "unicidad"):
            ComprobanteImporter(path).import_all()

        path = self.path()
        rows["comprobantes_comprobante"] = [
            {
                "id": 1, "tipo": "REMI", "serie": "00001",
                "numero_inicial": 10, "proximo_numero": 9,
                "numero_final": 100,
            }
        ]
        create_domain_source(path, (ComprobanteImporter,), rows)
        with self.assertRaisesRegex(MasterImportError, "fuera del rango"):
            ComprobanteImporter(path).import_all()

    def test_invalid_cliente_web_fk_aborts(self):
        path = self.path()
        rows = {
            "web_clientes_clienteweb": [
                {
                    "id": 1, "telefono": "", "activo": 1,
                    "email_verificado": 0, "acepta_terminos": 0,
                    "fecha_alta": "2020-01-01 00:00:00+00:00",
                    "ultimo_acceso": None, "cliente_id": None,
                    "user_id": 999,
                }
            ]
        }
        create_domain_source(path, (ClienteWebImporter,), rows)
        with self.assertRaisesRegex(MasterImportError, "FK inválidas"):
            ClienteWebImporter(path).import_all()

    def test_destination_empty_and_signals(self):
        path = self.path()
        rows = {
            "comprobantes_comprobante": [
                {
                    "id": 1, "tipo": "PRES", "serie": "00001",
                    "numero_inicial": 1, "proximo_numero": 2,
                    "numero_final": 100,
                }
            ]
        }
        create_domain_source(path, (ComprobanteImporter,), rows)
        pre_receiver, post_receiver = Mock(), Mock()
        pre_save.connect(pre_receiver, sender=Comprobante)
        post_save.connect(post_receiver, sender=Comprobante)
        try:
            ComprobanteImporter(path).import_all()
        finally:
            pre_save.disconnect(pre_receiver, sender=Comprobante)
            post_save.disconnect(post_receiver, sender=Comprobante)
        pre_receiver.assert_not_called()
        post_receiver.assert_not_called()

        with self.assertRaisesRegex(MasterImportError, "no está vacío"):
            ComprobanteImporter(path).import_all()
