"""Importación exclusiva de ``auth_user`` desde SQLite legacy."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import timezone as datetime_timezone
from pathlib import Path
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .base import BaseImporter


class UserImportError(Exception):
    """Los usuarios legacy no pueden importarse de forma segura."""


@dataclass
class UserImportReport:
    source_table: str = "auth_user"
    source_count: int = 0
    imported_count: int = 0
    batch_count: int = 0
    min_pk: int | None = None
    max_pk: int | None = None
    preserved_fields: tuple[str, ...] = ()
    ignored_optional_fields: tuple[str, ...] = ()
    status: str = "pending"

    def as_dict(self) -> dict:
        return asdict(self)


class UserImporter(BaseImporter):
    """Importa User conservando identidad y credenciales históricas."""

    table_name = "auth_user"
    required_columns = frozenset(
        {
            "id",
            "password",
            "last_login",
            "is_superuser",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "is_active",
            "date_joined",
        }
    )
    optional_timestamp_columns = frozenset({"created", "updated"})

    def __init__(
        self,
        database_path: str | Path,
        *,
        batch_size: int = 500,
        using: str = "default",
        user_model=None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size debe ser mayor que cero.")
        self.database_path = Path(database_path).resolve()
        self.batch_size = batch_size
        self.using = using
        self.user_model = user_model or get_user_model()
        self.source_columns: frozenset[str] = frozenset()
        self.import_fields: tuple[str, ...] = ()
        self.report = UserImportReport()
        self._prepared = False
        self._validated = False

    def _connect(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise UserImportError(f"No existe SQLite: {self.database_path}")
        uri = f"file:{quote(str(self.database_path))}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection
        except sqlite3.DatabaseError as exc:
            raise UserImportError(f"No se pudo abrir SQLite en modo lectura: {exc}") from exc

    def prepare(self) -> UserImportReport:
        try:
            with closing(self._connect()) as connection:
                table = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = ?
                    """,
                    (self.table_name,),
                ).fetchone()
                if table is None:
                    raise UserImportError("Falta la tabla legacy auth_user.")
                self.source_columns = frozenset(
                    row["name"]
                    for row in connection.execute('PRAGMA table_info("auth_user")')
                )
                missing = sorted(self.required_columns - self.source_columns)
                if missing:
                    raise UserImportError(
                        "Faltan columnas requeridas en auth_user: "
                        + ", ".join(missing)
                    )
                source_count, min_pk, max_pk = connection.execute(
                    'SELECT COUNT(*), MIN("id"), MAX("id") FROM "auth_user"'
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise UserImportError(f"No se pudo inspeccionar auth_user: {exc}") from exc

        target_fields = {
            field.name
            for field in self.user_model._meta.concrete_fields
        }
        optional = self.optional_timestamp_columns & self.source_columns
        included_optional = optional & target_fields
        ignored_optional = optional - target_fields
        self.import_fields = tuple(
            sorted(self.required_columns | included_optional)
        )
        self.report = UserImportReport(
            source_count=source_count,
            min_pk=min_pk,
            max_pk=max_pk,
            preserved_fields=self.import_fields,
            ignored_optional_fields=tuple(sorted(ignored_optional)),
            status="prepared",
        )
        self._prepared = True
        return self.report

    def validate(self) -> UserImportReport:
        if not self._prepared:
            raise UserImportError("Debe ejecutarse prepare() antes de validate().")
        try:
            with closing(self._connect()) as connection:
                duplicate_pks = [
                    row["id"]
                    for row in connection.execute(
                        """
                        SELECT id
                        FROM auth_user
                        GROUP BY id
                        HAVING COUNT(*) > 1
                        ORDER BY id
                        LIMIT 20
                        """
                    )
                ]
                duplicate_usernames = [
                    row["username"]
                    for row in connection.execute(
                        """
                        SELECT username
                        FROM auth_user
                        GROUP BY username
                        HAVING COUNT(*) > 1
                        ORDER BY username
                        LIMIT 20
                        """
                    )
                ]
                invalid_pks = [
                    row["id"]
                    for row in connection.execute(
                        'SELECT "id" FROM "auth_user" WHERE "id" < 1 LIMIT 20'
                    )
                ]
        except sqlite3.DatabaseError as exc:
            raise UserImportError(f"No se pudo validar auth_user: {exc}") from exc
        if duplicate_pks:
            raise UserImportError(f"PK duplicadas en auth_user: {duplicate_pks}")
        if duplicate_usernames:
            raise UserImportError(
                f"Username duplicados en auth_user: {duplicate_usernames}"
            )
        if invalid_pks:
            raise UserImportError(f"PK inválidas en auth_user: {invalid_pks}")
        if self.user_model._default_manager.using(self.using).exists():
            raise UserImportError("La tabla destino auth_user no está vacía.")
        self._validated = True
        self.report.status = "validated"
        return self.report

    def iter_batches(self):
        if not self._validated:
            raise UserImportError("Debe ejecutarse validate() antes de leer lotes.")
        columns = ", ".join(f'"{name}"' for name in self.import_fields)
        last_pk = None
        try:
            with closing(self._connect()) as connection:
                while True:
                    if last_pk is None:
                        rows = connection.execute(
                            f"""
                            SELECT {columns}
                            FROM "auth_user"
                            ORDER BY "id"
                            LIMIT ?
                            """,
                            (self.batch_size,),
                        ).fetchall()
                    else:
                        rows = connection.execute(
                            f"""
                            SELECT {columns}
                            FROM "auth_user"
                            WHERE "id" > ?
                            ORDER BY "id"
                            LIMIT ?
                            """,
                            (last_pk, self.batch_size),
                        ).fetchall()
                    if not rows:
                        break
                    yield [dict(row) for row in rows]
                    last_pk = rows[-1]["id"]
        except sqlite3.DatabaseError as exc:
            raise UserImportError(f"No se pudieron leer usuarios legacy: {exc}") from exc

    @staticmethod
    def _datetime(value, field_name: str, *, nullable: bool):
        if value is None and nullable:
            return None
        if not isinstance(value, str):
            raise UserImportError(f"{field_name} no contiene un datetime válido.")
        parsed = parse_datetime(value)
        if parsed is None:
            raise UserImportError(f"{field_name} no contiene un datetime válido.")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, datetime_timezone.utc)
        return parsed

    @staticmethod
    def _boolean(value, field_name: str) -> bool:
        if value not in (0, 1, False, True):
            raise UserImportError(f"{field_name} no contiene un booleano válido.")
        return bool(value)

    def _build_user(self, row: dict):
        try:
            pk = int(row["id"])
        except (TypeError, ValueError) as exc:
            raise UserImportError("auth_user.id no contiene una PK válida.") from exc
        if pk < 1:
            raise UserImportError("auth_user.id debe ser mayor que cero.")
        values = {
            "id": pk,
            "password": str(row["password"]),
            "last_login": self._datetime(
                row["last_login"], "last_login", nullable=True
            ),
            "is_superuser": self._boolean(row["is_superuser"], "is_superuser"),
            "username": str(row["username"]),
            "first_name": str(row["first_name"]),
            "last_name": str(row["last_name"]),
            "email": str(row["email"]),
            "is_staff": self._boolean(row["is_staff"], "is_staff"),
            "is_active": self._boolean(row["is_active"], "is_active"),
            "date_joined": self._datetime(
                row["date_joined"], "date_joined", nullable=False
            ),
        }
        for field_name in self.optional_timestamp_columns:
            if field_name in self.import_fields:
                values[field_name] = self._datetime(
                    row[field_name], field_name, nullable=True
                )
        return self.user_model(**values)

    def import_batch(self, batch) -> int:
        if not self._validated:
            raise UserImportError("Debe ejecutarse validate() antes de importar.")
        instances = [self._build_user(row) for row in batch]
        if not instances:
            return 0
        self.user_model._default_manager.using(self.using).bulk_create(
            instances,
            batch_size=self.batch_size,
        )
        self.report.imported_count += len(instances)
        self.report.batch_count += 1
        return len(instances)

    def finalize(self) -> UserImportReport:
        if self.report.imported_count != self.report.source_count:
            raise UserImportError(
                "La cantidad importada no coincide con el origen legacy."
            )
        imported = self.user_model._default_manager.using(self.using)
        target_stats = imported.aggregate(
            count=Count("pk"),
            min_pk=Min("pk"),
            max_pk=Max("pk"),
        )
        if (
            target_stats["count"] != self.report.source_count
            or target_stats["min_pk"] != self.report.min_pk
            or target_stats["max_pk"] != self.report.max_pk
        ):
            raise UserImportError("La verificación final de auth_user falló.")
        self.report.status = "completed"
        return self.report

    def import_all(self) -> UserImportReport:
        """Ejecuta sólo el dominio User en una única transacción atómica."""
        with transaction.atomic(using=self.using):
            self.prepare()
            self.validate()
            for batch in self.iter_batches():
                self.import_batch(batch)
            return self.finalize()
