"""Plan declarativo de secuencias; no ejecuta SQL."""

from __future__ import annotations

from django.db import transaction
from django.db.models import AutoField

from .schema import ACTION_GENERATED, ACTION_IMPORT, ID_GENERATED, ID_PRESERVE


class SequencePlanner:
    def build(self, manifest) -> list[dict]:
        entries = []
        seen = set()
        for mapping in manifest.mappings:
            if (
                not mapping.target_model
                or mapping.target_model in seen
                or mapping.action not in {ACTION_IMPORT, ACTION_GENERATED}
                or mapping.id_policy not in {ID_PRESERVE, ID_GENERATED}
            ):
                continue
            seen.add(mapping.target_model)
            entries.append(
                {
                    "target_model": mapping.target_model,
                    "source_table": mapping.source_table,
                    "id_policy": mapping.id_policy,
                    "action": "reset_after_import",
                }
            )
        return entries


class SequenceAdjustmentError(Exception):
    pass


class PostgresSequenceManager:
    """Resuelve y ajusta secuencias mediante PostgreSQL, sin nombres fijos."""

    def __init__(self, connection):
        self.connection = connection

    def adjust(self, models) -> list[dict]:
        if self.connection.vendor != "postgresql":
            raise SequenceAdjustmentError(
                "El ajuste de secuencias requiere PostgreSQL."
            )
        reports = []
        seen_tables = set()
        with transaction.atomic(using=self.connection.alias):
            with self.connection.cursor() as cursor:
                for model in models:
                    table = model._meta.db_table
                    pk = model._meta.pk
                    if table in seen_tables or not isinstance(pk, AutoField):
                        continue
                    seen_tables.add(table)
                    cursor.execute(
                        "SELECT pg_get_serial_sequence(%s, %s)",
                        [table, pk.column],
                    )
                    sequence = cursor.fetchone()[0]
                    if not sequence:
                        continue
                    quoted_table = self.connection.ops.quote_name(table)
                    quoted_pk = self.connection.ops.quote_name(pk.column)
                    cursor.execute(
                        f"SELECT MAX({quoted_pk}) FROM {quoted_table}"
                    )
                    maximum = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT setval(%s, %s, %s)",
                        [sequence, maximum if maximum is not None else 1, maximum is not None],
                    )
                    schema, name = (
                        sequence.split(".", 1)
                        if "." in sequence
                        else ("public", sequence)
                    )
                    clean_schema = schema.strip('"')
                    clean_name = name.strip('"')
                    quoted_sequence = (
                        f"{self.connection.ops.quote_name(clean_schema)}."
                        f"{self.connection.ops.quote_name(clean_name)}"
                    )
                    cursor.execute(
                        f"SELECT last_value, is_called FROM {quoted_sequence}"
                    )
                    verified = cursor.fetchone()
                    if verified is None:
                        raise SequenceAdjustmentError(
                            f"No se pudo verificar la secuencia {sequence}."
                        )
                    expected_next = (maximum + 1) if maximum is not None else 1
                    reports.append(
                        {
                            "model": model._meta.label,
                            "table": table,
                            "sequence": sequence,
                            "max_pk": maximum,
                            "next_value": expected_next,
                            "last_value": verified[0],
                            "is_called": verified[1],
                            "verified": (
                                verified[0]
                                == (maximum if maximum is not None else 1)
                                and verified[1] is (maximum is not None)
                            ),
                        }
                    )
                    if not reports[-1]["verified"]:
                        raise SequenceAdjustmentError(
                            f"Estado inesperado de secuencia {sequence}."
                        )
        return reports
