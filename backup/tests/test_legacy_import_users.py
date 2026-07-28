import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.test import TestCase

from backup.legacy.importers.users import UserImporter, UserImportError


USER_COLUMNS = """
    id INTEGER PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    last_login DATETIME NULL,
    is_superuser BOOL NOT NULL,
    username VARCHAR(150) NOT NULL UNIQUE,
    first_name VARCHAR(150) NOT NULL,
    last_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,
    is_staff BOOL NOT NULL,
    is_active BOOL NOT NULL,
    date_joined DATETIME NOT NULL
"""


def legacy_user(pk=7, **overrides):
    values = {
        "id": pk,
        "password": "pbkdf2_sha256$260000$salt$historicalhash",
        "last_login": "2021-05-06 13:14:15+00:00",
        "is_superuser": 1,
        "username": f"legacy-{pk}",
        "first_name": "Nombre",
        "last_name": "Histórico",
        "email": f"legacy-{pk}@example.invalid",
        "is_staff": 1,
        "is_active": 1,
        "date_joined": "2019-02-03 04:05:06+00:00",
    }
    values.update(overrides)
    return values


def create_legacy_database(path: Path, rows=(), columns=USER_COLUMNS):
    connection = sqlite3.connect(path)
    connection.execute(f"CREATE TABLE auth_user ({columns})")
    for row in rows:
        names = tuple(row)
        placeholders = ", ".join("?" for _ in names)
        connection.execute(
            f"INSERT INTO auth_user ({', '.join(names)}) VALUES ({placeholders})",
            tuple(row[name] for name in names),
        )
    connection.commit()
    connection.close()


class UserImporterTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_path = Path(self.temporary.name) / "database.sqlite3"
        self.User = get_user_model()

    def test_imports_user_and_reports_statistics(self):
        create_legacy_database(
            self.database_path,
            [legacy_user(7), legacy_user(11, is_staff=0, is_superuser=0)],
        )

        report = UserImporter(self.database_path, batch_size=1).import_all()

        self.assertEqual(self.User.objects.count(), 2)
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.source_count, 2)
        self.assertEqual(report.imported_count, 2)
        self.assertEqual(report.batch_count, 2)
        self.assertEqual((report.min_pk, report.max_pk), (7, 11))

    def test_empty_source_imports_no_users(self):
        create_legacy_database(self.database_path)

        report = UserImporter(self.database_path).import_all()

        self.assertEqual(report.imported_count, 0)
        self.assertFalse(self.User.objects.exists())

    def test_preserves_password_hash_and_primary_key(self):
        source = legacy_user(37)
        create_legacy_database(self.database_path, [source])

        UserImporter(self.database_path).import_all()

        user = self.User.objects.get()
        self.assertEqual(user.pk, 37)
        self.assertEqual(user.password, source["password"])

    def test_preserves_historical_timestamps(self):
        source = legacy_user(8)
        create_legacy_database(self.database_path, [source])

        UserImporter(self.database_path).import_all()

        user = self.User.objects.get(pk=8)
        self.assertEqual(
            user.last_login,
            datetime(2021, 5, 6, 13, 14, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(
            user.date_joined,
            datetime(2019, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
        )

    def test_bulk_import_does_not_emit_save_signals(self):
        create_legacy_database(self.database_path, [legacy_user()])
        pre_receiver = Mock()
        post_receiver = Mock()
        pre_save.connect(pre_receiver, sender=self.User)
        post_save.connect(post_receiver, sender=self.User)
        self.addCleanup(pre_save.disconnect, pre_receiver, sender=self.User)
        self.addCleanup(post_save.disconnect, post_receiver, sender=self.User)

        UserImporter(self.database_path).import_all()

        pre_receiver.assert_not_called()
        post_receiver.assert_not_called()

    def test_missing_required_column_aborts(self):
        columns = USER_COLUMNS.replace(
            "email VARCHAR(254) NOT NULL,\n", ""
        )
        create_legacy_database(self.database_path, columns=columns)

        with self.assertRaisesRegex(UserImportError, "email"):
            UserImporter(self.database_path).import_all()

        self.assertFalse(self.User.objects.exists())

    def test_duplicate_primary_key_aborts(self):
        columns = USER_COLUMNS.replace("id INTEGER PRIMARY KEY", "id INTEGER")
        first = legacy_user(5)
        second = legacy_user(5, username="otro-legacy")
        create_legacy_database(self.database_path, [first, second], columns=columns)

        with self.assertRaisesRegex(UserImportError, "PK duplicadas"):
            UserImporter(self.database_path).import_all()

        self.assertFalse(self.User.objects.exists())

    def test_rolls_back_all_batches_when_later_batch_is_invalid(self):
        create_legacy_database(
            self.database_path,
            [
                legacy_user(1),
                legacy_user(2, date_joined="fecha-inválida"),
            ],
        )

        with self.assertRaisesRegex(UserImportError, "date_joined"):
            UserImporter(self.database_path, batch_size=1).import_all()

        self.assertFalse(self.User.objects.exists())
