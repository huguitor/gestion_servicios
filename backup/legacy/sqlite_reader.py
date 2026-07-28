"""Lectura estrictamente de solo lectura de una base SQLite legacy."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote


class SQLiteAuditError(Exception):
    """La base SQLite no pudo inspeccionarse de forma segura."""


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


class LegacySQLiteReader:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path).resolve()

    def inspect(self) -> dict:
        if not self.database_path.is_file():
            raise SQLiteAuditError(
                f"No existe la base SQLite: {self.database_path}"
            )

        uri = f"file:{quote(str(self.database_path))}?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return self._inspect_connection(connection)
        except sqlite3.DatabaseError as exc:
            raise SQLiteAuditError(f"SQLite inválida o corrupta: {exc}") from exc
        finally:
            if "connection" in locals():
                connection.close()

    def _inspect_connection(self, connection: sqlite3.Connection) -> dict:
        integrity_rows = [
            row[0] for row in connection.execute("PRAGMA integrity_check")
        ]
        foreign_key_rows = [
            {
                "table": row[0],
                "rowid": row[1],
                "parent": row[2],
                "foreign_key_index": row[3],
            }
            for row in connection.execute("PRAGMA foreign_key_check")
        ]

        objects = [
            dict(row)
            for row in connection.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE type IN ('table', 'index', 'trigger', 'view')
                ORDER BY type, name
                """
            )
        ]
        table_names = [
            row["name"]
            for row in objects
            if row["type"] == "table" and row["name"] != "sqlite_sequence"
        ]

        tables = {}
        for table_name in table_names:
            identifier = _quote_identifier(table_name)
            columns = [
                {
                    "position": row["cid"],
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key_position": row["pk"],
                }
                for row in connection.execute(f"PRAGMA table_info({identifier})")
            ]
            foreign_keys = [
                {
                    "id": row["id"],
                    "position": row["seq"],
                    "target_table": row["table"],
                    "from_column": row["from"],
                    "to_column": row["to"],
                    "on_update": row["on_update"],
                    "on_delete": row["on_delete"],
                    "match": row["match"],
                }
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({identifier})"
                )
            ]
            indexes = []
            for row in connection.execute(f"PRAGMA index_list({identifier})"):
                index_name = row["name"]
                index_identifier = _quote_identifier(index_name)
                indexes.append(
                    {
                        "name": index_name,
                        "unique": bool(row["unique"]),
                        "origin": row["origin"],
                        "partial": bool(row["partial"]),
                        "columns": [
                            info["name"]
                            for info in connection.execute(
                                f"PRAGMA index_info({index_identifier})"
                            )
                        ],
                    }
                )
            count = connection.execute(
                f"SELECT COUNT(*) FROM {identifier}"
            ).fetchone()[0]
            create_sql = next(
                (
                    item["sql"]
                    for item in objects
                    if item["type"] == "table" and item["name"] == table_name
                ),
                None,
            )
            tables[table_name] = {
                "count": count,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "create_sql": create_sql,
            }

        sequences = []
        sequence_exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'sqlite_sequence'
            """
        ).fetchone()
        if sequence_exists:
            sequences = [
                {"table": row[0], "value": row[1]}
                for row in connection.execute(
                    "SELECT name, seq FROM sqlite_sequence ORDER BY name"
                )
            ]

        migrations = []
        if "django_migrations" in tables:
            migrations = [
                {"app": row[0], "name": row[1], "applied": row[2]}
                for row in connection.execute(
                    """
                    SELECT app, name, applied
                    FROM django_migrations
                    ORDER BY app, applied
                    """
                )
            ]

        return {
            "database_path": str(self.database_path),
            "sqlite_version": connection.execute(
                "SELECT sqlite_version()"
            ).fetchone()[0],
            "user_version": connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0],
            "application_id": connection.execute(
                "PRAGMA application_id"
            ).fetchone()[0],
            "integrity_check": integrity_rows,
            "integrity_ok": integrity_rows == ["ok"],
            "foreign_key_check": foreign_key_rows,
            "foreign_keys_ok": not foreign_key_rows,
            "tables": tables,
            "objects": objects,
            "sequences": sequences,
            "migrations": migrations,
        }

    def file_references(self, fields: dict[str, tuple[str, ...]]) -> list[dict]:
        """Obtiene sólo rutas declaradas en campos multimedia conocidos."""
        uri = f"file:{quote(str(self.database_path))}?mode=ro&immutable=1"
        references = []
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.execute("PRAGMA query_only = ON")
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            for table_name, column_names in fields.items():
                if table_name not in existing_tables:
                    continue
                identifier = _quote_identifier(table_name)
                existing_columns = {
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({identifier})"
                    )
                }
                for column_name in column_names:
                    if column_name not in existing_columns:
                        continue
                    column_identifier = _quote_identifier(column_name)
                    rows = connection.execute(
                        f"""
                        SELECT id, {column_identifier}
                        FROM {identifier}
                        WHERE {column_identifier} IS NOT NULL
                          AND TRIM({column_identifier}) != ''
                        """
                    )
                    references.extend(
                        {
                            "table": table_name,
                            "record_id": row[0],
                            "field": column_name,
                            "path": str(row[1]).replace("\\", "/").lstrip("/"),
                        }
                        for row in rows
                    )
        except sqlite3.DatabaseError as exc:
            raise SQLiteAuditError(
                f"No se pudieron leer referencias multimedia: {exc}"
            ) from exc
        finally:
            if "connection" in locals():
                connection.close()
        return references
