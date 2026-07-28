from django.db import connection
from django.test import TransactionTestCase

from backup.legacy.sequences import PostgresSequenceManager
from categorias.models import Categoria


class LegacySequenceTests(TransactionTestCase):
    reset_sequences = True

    def test_adjusts_sequence_after_preserved_primary_key(self):
        Categoria.objects.bulk_create(
            [Categoria(id=40, nombre="Legacy cuarenta")]
        )

        report = PostgresSequenceManager(connection).adjust([Categoria])
        created = Categoria.objects.create(nombre="Siguiente")

        self.assertEqual(created.pk, 41)
        self.assertEqual(report[0]["max_pk"], 40)
        self.assertEqual(report[0]["next_value"], 41)

    def test_empty_table_sequence_starts_at_one(self):
        report = PostgresSequenceManager(connection).adjust([Categoria])
        created = Categoria.objects.create(nombre="Primera")

        self.assertEqual(created.pk, 1)
        self.assertIsNone(report[0]["max_pk"])
        self.assertEqual(report[0]["next_value"], 1)
