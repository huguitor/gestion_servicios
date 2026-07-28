"""Importación exclusiva de ``clientes_cliente``."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import timezone as datetime_timezone
from pathlib import Path
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from clientes.models import Cliente

from .base import BaseImporter


class ClienteImportError(Exception):
    """Los clientes legacy no pueden importarse de forma segura."""


@dataclass
class ClienteImportReport:
    source_table: str = "clientes_cliente"
    read_count: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    batch_count: int = 0
    min_pk: int | None = None
    max_pk: int | None = None
    warnings: list[str] = field(default_factory=list)
    defaults_applied: dict = field(default_factory=dict)
    status: str = "pending"

    def as_dict(self) -> dict:
        return asdict(self)


class ClientesImporter(BaseImporter):
    """Importa Cliente conservando PK y valores históricos."""

    table_name = "clientes_cliente"
    legacy_columns = (
        "id",
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
        "activo",
        "creado",
        "actualizado",
    )
    required_columns = frozenset(legacy_columns)
    nullable_text_fields = frozenset(
        {
            "apellido",
            "documento",
            "telefono",
            "email",
            "direccion",
            "ciudad",
            "provincia",
        }
    )
    historical_timestamp_fields = ("creado", "actualizado")

    def __init__(
        self,
        database_path: str | Path,
        *,
        batch_size: int = 500,
        using: str = "default",
        model=Cliente,
    ):
        if batch_size < 1:
            raise ValueError("batch_size debe ser mayor que cero.")
        self.database_path = Path(database_path).resolve()
        self.batch_size = batch_size
        self.using = using
        self.model = model
        self.source_columns: frozenset[str] = frozenset()
        self.source_foreign_keys: tuple[dict, ...] = ()
        self.import_columns: tuple[str, ...] = ()
        self.report = ClienteImportReport()
        self._prepared = False
        self._validated = False

    def _connect(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise ClienteImportError(f"No existe SQLite: {self.database_path}")
        uri = f"file:{quote(str(self.database_path))}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection
        except sqlite3.DatabaseError as exc:
            raise ClienteImportError(
                f"No se pudo abrir SQLite en modo lectura: {exc}"
            ) from exc

    def prepare(self) -> ClienteImportReport:
        try:
            with closing(self._connect()) as connection:
                table = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = ?
                    """,
                    (self.table_name,),
                ).fetchone()
                if table is None:
                    raise ClienteImportError(
                        "Falta la tabla legacy clientes_cliente."
                    )
                self.source_columns = frozenset(
                    row["name"]
                    for row in connection.execute(
                        'PRAGMA table_info("clientes_cliente")'
                    )
                )
                self.source_foreign_keys = tuple(
                    {
                        "column": row["from"],
                        "target_table": row["table"],
                        "target_column": row["to"],
                    }
                    for row in connection.execute(
                        'PRAGMA foreign_key_list("clientes_cliente")'
                    )
                )
                missing = sorted(self.required_columns - self.source_columns)
                if missing:
                    raise ClienteImportError(
                        "Faltan columnas requeridas en clientes_cliente: "
                        + ", ".join(missing)
                    )
                source_count, min_pk, max_pk = connection.execute(
                    'SELECT COUNT(*), MIN("id"), MAX("id") '
                    'FROM "clientes_cliente"'
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise ClienteImportError(
                f"No se pudo inspeccionar clientes_cliente: {exc}"
            ) from exc

        target_fields = {
            item.name for item in self.model._meta.concrete_fields
        }
        missing_target = sorted(
            (self.required_columns | {"plazo_cobro_dias"}) - target_fields
        )
        if missing_target:
            raise ClienteImportError(
                "El modelo Cliente actual no contiene: "
                + ", ".join(missing_target)
            )
        self.import_columns = self.legacy_columns
        defaults = {}
        if "plazo_cobro_dias" not in self.source_columns:
            defaults["plazo_cobro_dias"] = {
                "value": 0,
                "applied_count": source_count,
            }
        self.report = ClienteImportReport(
            min_pk=min_pk,
            max_pk=max_pk,
            defaults_applied=defaults,
            status="prepared",
        )
        self._prepared = True
        return self.report

    def _validate_foreign_keys(self) -> None:
        if self.source_foreign_keys:
            raise ClienteImportError(
                "clientes_cliente contiene FK no contempladas por el manifiesto: "
                + ", ".join(
                    f"{item['column']}->{item['target_table']}.{item['target_column']}"
                    for item in self.source_foreign_keys
                )
            )
        foreign_keys = [
            item.name
            for item in self.model._meta.concrete_fields
            if item.is_relation and item.many_to_one
        ]
        if foreign_keys:
            raise ClienteImportError(
                "El modelo Cliente incorporó FK no contempladas por el manifiesto: "
                + ", ".join(sorted(foreign_keys))
            )

    def validate(self) -> ClienteImportReport:
        if not self._prepared:
            raise ClienteImportError(
                "Debe ejecutarse prepare() antes de validate()."
            )
        try:
            with closing(self._connect()) as connection:
                null_pks = connection.execute(
                    'SELECT COUNT(*) FROM "clientes_cliente" WHERE "id" IS NULL'
                ).fetchone()[0]
                duplicate_pks = [
                    row["id"]
                    for row in connection.execute(
                        """
                        SELECT id FROM clientes_cliente
                        GROUP BY id HAVING COUNT(*) > 1
                        ORDER BY id LIMIT 20
                        """
                    )
                ]
                duplicate_documents = [
                    row["documento"]
                    for row in connection.execute(
                        """
                        SELECT documento FROM clientes_cliente
                        WHERE documento IS NOT NULL
                        GROUP BY documento HAVING COUNT(*) > 1
                        ORDER BY documento LIMIT 20
                        """
                    )
                ]
        except sqlite3.DatabaseError as exc:
            raise ClienteImportError(
                f"No se pudo validar clientes_cliente: {exc}"
            ) from exc
        if null_pks:
            raise ClienteImportError(
                f"PK nulas en clientes_cliente: {null_pks}"
            )
        if duplicate_pks:
            raise ClienteImportError(
                f"PK duplicadas en clientes_cliente: {duplicate_pks}"
            )
        if duplicate_documents:
            raise ClienteImportError(
                "Conflicto en campo único documento: "
                + ", ".join(repr(value) for value in duplicate_documents)
            )
        self._validate_foreign_keys()
        if self.model._default_manager.using(self.using).exists():
            raise ClienteImportError(
                "La tabla destino clientes_cliente no está vacía."
            )
        self._validated = True
        self.report.status = "validated"
        return self.report

    def iter_batches(self):
        if not self._validated:
            raise ClienteImportError(
                "Debe ejecutarse validate() antes de leer lotes."
            )
        columns = list(self.import_columns)
        if "plazo_cobro_dias" in self.source_columns:
            columns.append("plazo_cobro_dias")
        select_columns = ", ".join(f'"{name}"' for name in columns)
        last_pk = None
        try:
            with closing(self._connect()) as connection:
                while True:
                    if last_pk is None:
                        rows = connection.execute(
                            f"""
                            SELECT {select_columns}
                            FROM "clientes_cliente"
                            ORDER BY "id"
                            LIMIT ?
                            """,
                            (self.batch_size,),
                        ).fetchall()
                    else:
                        rows = connection.execute(
                            f"""
                            SELECT {select_columns}
                            FROM "clientes_cliente"
                            WHERE "id" > ?
                            ORDER BY "id"
                            LIMIT ?
                            """,
                            (last_pk, self.batch_size),
                        ).fetchall()
                    if not rows:
                        break
                    batch = [dict(row) for row in rows]
                    self.report.read_count += len(batch)
                    yield batch
                    last_pk = rows[-1]["id"]
        except sqlite3.DatabaseError as exc:
            raise ClienteImportError(
                f"No se pudieron leer clientes legacy: {exc}"
            ) from exc

    @staticmethod
    def _datetime(value, field_name: str):
        if not isinstance(value, str):
            raise ClienteImportError(
                f"{field_name} no contiene un datetime válido."
            )
        parsed = parse_datetime(value)
        if parsed is None:
            raise ClienteImportError(
                f"{field_name} no contiene un datetime válido."
            )
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, datetime_timezone.utc)
        return parsed

    @staticmethod
    def _boolean(value, field_name: str) -> bool:
        if value not in (0, 1, False, True):
            raise ClienteImportError(
                f"{field_name} no contiene un booleano válido."
            )
        return bool(value)

    def _text(self, row: dict, field_name: str):
        value = row[field_name]
        if value is None and field_name in self.nullable_text_fields:
            return None
        if not isinstance(value, str):
            raise ClienteImportError(
                f"{field_name} no contiene texto válido."
            )
        return value

    def _build_cliente(self, row: dict):
        try:
            pk = int(row["id"])
            plazo_cobro_dias = int(row.get("plazo_cobro_dias", 0))
        except (TypeError, ValueError) as exc:
            raise ClienteImportError(
                "Cliente contiene un entero inválido."
            ) from exc
        if pk < 1:
            raise ClienteImportError("Cliente.id debe ser mayor que cero.")
        if plazo_cobro_dias < 0:
            raise ClienteImportError(
                "plazo_cobro_dias no puede ser negativo."
            )

        values = {
            "id": pk,
            "tipo": self._text(row, "tipo"),
            "nombre": self._text(row, "nombre"),
            "apellido": self._text(row, "apellido"),
            "documento": self._text(row, "documento"),
            "condicion_iva": self._text(row, "condicion_iva"),
            "telefono": self._text(row, "telefono"),
            "email": self._text(row, "email"),
            "direccion": self._text(row, "direccion"),
            "ciudad": self._text(row, "ciudad"),
            "provincia": self._text(row, "provincia"),
            "pais": self._text(row, "pais"),
            "plazo_cobro_dias": plazo_cobro_dias,
            "activo": self._boolean(row["activo"], "activo"),
            "creado": self._datetime(row["creado"], "creado"),
            "actualizado": self._datetime(row["actualizado"], "actualizado"),
        }
        documento = values["documento"]
        if documento is not None and not re.fullmatch(r"\d{8}|\d{11}", documento):
            raise ClienteImportError(
                f"Cliente {pk}: documento inválido."
            )
        if values["tipo"] == "fisica" and values["apellido"] is None:
            raise ClienteImportError(
                f"Cliente {pk}: apellido requerido para persona física."
            )
        instance = self.model(**values)
        try:
            instance.full_clean(
                validate_unique=False,
                validate_constraints=False,
            )
        except ValidationError as exc:
            raise ClienteImportError(
                f"Cliente {pk} no supera validaciones: {exc.message_dict}"
            ) from exc
        return instance

    def import_batch(self, batch) -> int:
        if not self._validated:
            raise ClienteImportError(
                "Debe ejecutarse validate() antes de importar."
            )
        instances = [self._build_cliente(row) for row in batch]
        if not instances:
            return 0
        historical_timestamps = [
            (instance.creado, instance.actualizado)
            for instance in instances
        ]
        manager = self.model._default_manager.using(self.using)
        manager.bulk_create(instances, batch_size=self.batch_size)
        for instance, (creado, actualizado) in zip(
            instances, historical_timestamps
        ):
            instance.creado = creado
            instance.actualizado = actualizado
        manager.bulk_update(
            instances,
            list(self.historical_timestamp_fields),
            batch_size=self.batch_size,
        )
        self.report.imported_count += len(instances)
        self.report.batch_count += 1
        return len(instances)

    def finalize(self) -> ClienteImportReport:
        if self.report.read_count != self.report.imported_count:
            raise ClienteImportError(
                "La cantidad leída no coincide con la importada."
            )
        manager = self.model._default_manager.using(self.using)
        target = manager.aggregate(
            count=Count("pk"),
            min_pk=Min("pk"),
            max_pk=Max("pk"),
        )
        if (
            target["count"] != self.report.imported_count
            or target["min_pk"] != self.report.min_pk
            or target["max_pk"] != self.report.max_pk
        ):
            raise ClienteImportError(
                "La verificación final de clientes_cliente falló."
            )
        self.report.status = "completed"
        return self.report

    def import_all(self) -> ClienteImportReport:
        """Ejecuta sólo Cliente en una única transacción atómica."""
        with transaction.atomic(using=self.using):
            self.prepare()
            self.validate()
            for batch in self.iter_batches():
                self.import_batch(batch)
            return self.finalize()


# Compatibilidad con el nombre declarado en el manifest de infraestructura.
ClienteImporter = ClientesImporter
