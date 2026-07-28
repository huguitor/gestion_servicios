import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class LegacyImportCommandTests(SimpleTestCase):
    databases = set()

    def options(self, root):
        return {
            "sqlite": str(root / "database.sqlite3"),
            "manifest": str(root / "audit"),
            "media_tar": str(root / "media.tar.gz"),
            "checksums": str(root / "SHA256SUMS.txt"),
            "reports": str(root / "reports"),
            "staging": str(root / "staging"),
        }

    @patch(
        "backup.management.commands.import_legacy_sqlite.LegacyMigrationRunner"
    )
    @patch(
        "backup.management.commands.import_legacy_sqlite.LegacyManifest.load"
    )
    def test_default_mode_is_validation_without_apply(
        self, load_manifest, runner_class
    ):
        manifest = SimpleNamespace(
            run_id="test",
            imported_mappings=(),
            source_count=lambda table: 0,
        )
        load_manifest.return_value = manifest
        runner_class.return_value.run.return_value = {
            "run_id": "test",
            "result": "validation_complete_without_writes",
        }
        output = StringIO()
        with tempfile.TemporaryDirectory() as temporary:
            call_command(
                "import_legacy_sqlite",
                stdout=output,
                **self.options(Path(temporary)),
            )

        kwargs = runner_class.call_args.kwargs
        self.assertFalse(kwargs["apply"])
        self.assertFalse(kwargs["allow_production"])
        self.assertIn("VALIDACIÓN COMPLETA SIN ESCRITURAS", output.getvalue())

    @patch(
        "backup.management.commands.import_legacy_sqlite.LegacyManifest.load"
    )
    def test_rejects_allow_production_without_apply(self, load_manifest):
        with tempfile.TemporaryDirectory() as temporary:
            options = self.options(Path(temporary))
            options["allow_production"] = True
            with self.assertRaisesRegex(CommandError, "requiere --apply"):
                call_command("import_legacy_sqlite", **options)
        load_manifest.assert_not_called()

    @patch(
        "backup.management.commands.import_legacy_sqlite.LegacyMigrationRunner"
    )
    @patch(
        "backup.management.commands.import_legacy_sqlite.LegacyManifest.load"
    )
    def test_failure_returns_management_command_error(
        self, load_manifest, runner_class
    ):
        load_manifest.return_value = SimpleNamespace(
            imported_mappings=(),
            source_count=lambda table: 0,
        )
        runner_class.return_value.run.side_effect = RuntimeError("stage failed")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(CommandError, "stage failed"):
                call_command(
                    "import_legacy_sqlite",
                    stderr=StringIO(),
                    **self.options(Path(temporary)),
                )
