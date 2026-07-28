"""Patrón común, acotado, para maestros legacy sin relaciones."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .base import BaseImporter


class MasterImportError(Exception):
    """Un maestro legacy no puede importarse de forma segura."""


@dataclass
class MasterImportReport:
    source_table: str
    target_model: str
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


class MasterModelImporter(BaseImporter):
    """Importador reusable sólo para tablas maestras sin FK."""

    table_name = ""
    model = None
    columns: tuple[str, ...] = ()
    nullable_fields: frozenset[str] = frozenset()
    boolean_fields: frozenset[str] = frozenset()
    integer_fields: frozenset[str] = frozenset()
    decimal_fields: frozenset[str] = frozenset()
    timestamp_fields: tuple[str, ...] = ("creado", "actualizado")
    unique_fields: tuple[str, ...] = ()

    def __init__(self, database_path, *, batch_size=500, using="default"):
        if batch_size < 1:
            raise ValueError("batch_size debe ser mayor que cero.")
        self.database_path = Path(database_path).resolve()
        self.batch_size = batch_size
        self.using = using
        self.source_columns = frozenset()
        self.report = MasterImportReport(
            source_table=self.table_name,
            target_model=self.model._meta.label,
        )
        self._prepared = False
        self._validated = False

    def _connect(self):
        if not self.database_path.is_file():
            raise MasterImportError(f"No existe SQLite: {self.database_path}")
        uri = f"file:{quote(str(self.database_path))}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection
        except sqlite3.DatabaseError as exc:
            raise MasterImportError(
                f"No se pudo abrir SQLite en modo lectura: {exc}"
            ) from exc

    def prepare(self):
        try:
            with closing(self._connect()) as connection:
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (self.table_name,),
                ).fetchone()
                if not exists:
                    raise MasterImportError(f"Falta la tabla {self.table_name}.")
                table_info = connection.execute(
                    f'PRAGMA table_info("{self.table_name}")'
                ).fetchall()
                self.source_columns = frozenset(row["name"] for row in table_info)
                missing = sorted(set(self.columns) - self.source_columns)
                if missing:
                    raise MasterImportError(
                        f"Faltan columnas en {self.table_name}: "
                        + ", ".join(missing)
                    )
                source_count, min_pk, max_pk = connection.execute(
                    f'SELECT COUNT(*), MIN("id"), MAX("id") '
                    f'FROM "{self.table_name}"'
                ).fetchone()
                source_fks = connection.execute(
                    f'PRAGMA foreign_key_list("{self.table_name}")'
                ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise MasterImportError(
                f"No se pudo inspeccionar {self.table_name}: {exc}"
            ) from exc
        if source_fks:
            raise MasterImportError(
                f"{self.table_name} contiene FK no contempladas."
            )
        target_fields = {field.name for field in self.model._meta.concrete_fields}
        missing_target = sorted(set(self.columns) - target_fields)
        if missing_target:
            raise MasterImportError(
                f"{self.model._meta.label} no contiene: "
                + ", ".join(missing_target)
            )
        target_fks = [
            field.name
            for field in self.model._meta.concrete_fields
            if field.is_relation and field.many_to_one
        ]
        if target_fks:
            raise MasterImportError(
                f"{self.model._meta.label} incorporó FK no contempladas."
            )
        self.report.min_pk = min_pk
        self.report.max_pk = max_pk
        self.report.status = "prepared"
        self._prepared = True
        return self.report

    def validate(self):
        if not self._prepared:
            raise MasterImportError("Debe ejecutarse prepare() antes de validate().")
        try:
            with closing(self._connect()) as connection:
                null_pks = connection.execute(
                    f'SELECT COUNT(*) FROM "{self.table_name}" WHERE id IS NULL'
                ).fetchone()[0]
                duplicate_pks = connection.execute(
                    f'SELECT id FROM "{self.table_name}" GROUP BY id '
                    f'HAVING COUNT(*) > 1 LIMIT 20'
                ).fetchall()
                unique_conflicts = {}
                for field_name in self.unique_fields:
                    rows = connection.execute(
                        f'SELECT "{field_name}" FROM "{self.table_name}" '
                        f'WHERE "{field_name}" IS NOT NULL '
                        f'GROUP BY "{field_name}" HAVING COUNT(*) > 1 LIMIT 20'
                    ).fetchall()
                    if rows:
                        unique_conflicts[field_name] = [row[0] for row in rows]
                self.validate_source(connection)
        except sqlite3.DatabaseError as exc:
            raise MasterImportError(
                f"No se pudo validar {self.table_name}: {exc}"
            ) from exc
        if null_pks:
            raise MasterImportError(f"PK nulas en {self.table_name}.")
        if duplicate_pks:
            raise MasterImportError(f"PK duplicadas en {self.table_name}.")
        if unique_conflicts:
            raise MasterImportError(
                f"Conflictos de unicidad en {self.table_name}: {unique_conflicts}"
            )
        if self.model._default_manager.using(self.using).exists():
            raise MasterImportError(
                f"El destino {self.model._meta.db_table} no está vacío."
            )
        self._validated = True
        self.report.status = "validated"
        return self.report

    def validate_source(self, connection):
        """Hook de validaciones cruzadas que no escriben."""

    def iter_batches(self):
        if not self._validated:
            raise MasterImportError("Debe ejecutarse validate() antes de leer lotes.")
        selected = ", ".join(f'"{name}"' for name in self.columns)
        last_pk = None
        try:
            with closing(self._connect()) as connection:
                while True:
                    if last_pk is None:
                        rows = connection.execute(
                            f'SELECT {selected} FROM "{self.table_name}" '
                            f'ORDER BY id LIMIT ?',
                            (self.batch_size,),
                        ).fetchall()
                    else:
                        rows = connection.execute(
                            f'SELECT {selected} FROM "{self.table_name}" '
                            f'WHERE id > ? ORDER BY id LIMIT ?',
                            (last_pk, self.batch_size),
                        ).fetchall()
                    if not rows:
                        break
                    batch = [dict(row) for row in rows]
                    self.report.read_count += len(batch)
                    yield batch
                    last_pk = rows[-1]["id"]
        except sqlite3.DatabaseError as exc:
            raise MasterImportError(
                f"No se pudo leer {self.table_name}: {exc}"
            ) from exc

    @staticmethod
    def _datetime(value, field_name):
        if not isinstance(value, str):
            raise MasterImportError(f"{field_name} no es un datetime válido.")
        parsed = parse_datetime(value)
        if parsed is None:
            raise MasterImportError(f"{field_name} no es un datetime válido.")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, datetime_timezone.utc)
        return parsed

    @staticmethod
    def _boolean(value, field_name):
        if value not in (0, 1, False, True):
            raise MasterImportError(f"{field_name} no es booleano.")
        return bool(value)

    def convert_value(self, field_name, value):
        if value is None:
            if field_name in self.nullable_fields:
                return None
            raise MasterImportError(f"{field_name} no admite NULL.")
        if field_name in self.boolean_fields:
            return self._boolean(value, field_name)
        if field_name in self.integer_fields or field_name == "id":
            try:
                converted = int(value)
            except (TypeError, ValueError) as exc:
                raise MasterImportError(f"{field_name} no es entero.") from exc
            if field_name == "id" and converted < 1:
                raise MasterImportError("La PK debe ser mayor que cero.")
            return converted
        if field_name in self.decimal_fields:
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise MasterImportError(f"{field_name} no es decimal.") from exc
        if field_name in self.timestamp_fields:
            return self._datetime(value, field_name)
        if not isinstance(value, str):
            raise MasterImportError(f"{field_name} no contiene texto válido.")
        return value

    def build_instance(self, row):
        values = {
            field_name: self.convert_value(field_name, row[field_name])
            for field_name in self.columns
        }
        instance = self.model(**values)
        try:
            instance.full_clean(validate_unique=False, validate_constraints=False)
        except ValidationError as exc:
            raise MasterImportError(
                f"{self.model._meta.label} {values['id']} inválido: "
                f"{exc.message_dict}"
            ) from exc
        return instance

    def import_batch(self, batch):
        if not self._validated:
            raise MasterImportError("Debe ejecutarse validate() antes de importar.")
        instances = [self.build_instance(row) for row in batch]
        if not instances:
            return 0
        historical = [
            tuple(getattr(instance, field) for field in self.timestamp_fields)
            for instance in instances
        ]
        manager = self.model._default_manager.using(self.using)
        manager.bulk_create(instances, batch_size=self.batch_size)
        if self.timestamp_fields:
            for instance, values in zip(instances, historical):
                for field_name, value in zip(self.timestamp_fields, values):
                    setattr(instance, field_name, value)
            manager.bulk_update(
                instances,
                list(self.timestamp_fields),
                batch_size=self.batch_size,
            )
        self.report.imported_count += len(instances)
        self.report.batch_count += 1
        return len(instances)

    def finalize(self):
        if self.report.read_count != self.report.imported_count:
            raise MasterImportError("Las cantidades leída e importada no coinciden.")
        stats = self.model._default_manager.using(self.using).aggregate(
            count=Count("pk"), min_pk=Min("pk"), max_pk=Max("pk")
        )
        if (
            stats["count"] != self.report.imported_count
            or stats["min_pk"] != self.report.min_pk
            or stats["max_pk"] != self.report.max_pk
        ):
            raise MasterImportError(
                f"La verificación final de {self.table_name} falló."
            )
        self.report.status = "completed"
        return self.report

    def import_all(self):
        with transaction.atomic(using=self.using):
            self.prepare()
            self.validate()
            for batch in self.iter_batches():
                self.import_batch(batch)
            return self.finalize()
