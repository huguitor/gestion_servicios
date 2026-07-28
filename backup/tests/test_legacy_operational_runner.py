import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from backup.legacy.pipeline import PipelineStage
from backup.legacy.runner import LegacyMigrationError, LegacyMigrationRunner
from backup.legacy.validators import ValidationResult


class FakeConnection:
    alias = "default"
    vendor = "postgresql"
    settings_dict = {"HOST": "db", "NAME": "test"}

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def check_constraints(self):
        return None


class FakeManifest:
    run_id = "operational-test"
    imported_mappings = ()
    media = {"references": [], "hashes": {"database.sqlite3": "safe"}}

    def source_count(self, table):
        return 0


class FakeSuite:
    def run(self, context):
        return [ValidationResult("preflight", "ok", "Correcto")]


class FakePlanner:
    def __init__(self, root):
        self.root = Path(root)

    def generate(self, manifest, validations, *, mode):
        output = self.root / manifest.run_id
        output.mkdir(parents=True)
        (output / "plan.json").write_text(
            json.dumps({"mode": mode}), encoding="utf-8"
        )
        return {"output_dir": str(output)}


class FakeMedia:
    calls = 0

    def __init__(self, **kwargs):
        pass

    def migrate(self):
        type(self).calls += 1
        return {"found": 0, "migrated": 0, "missing": []}


class FakeSequences:
    calls = 0

    def __init__(self, connection):
        pass

    def adjust(self, models):
        type(self).calls += 1
        return []


def importer(events, key, *, fail=False):
    class Importer:
        def __init__(self, sqlite_path, **kwargs):
            pass

        def import_all(self):
            events.append(key)
            if fail:
                raise RuntimeError(f"falló {key}")
            return SimpleNamespace(as_dict=lambda: {"imported": 0})

    return Importer


class LegacyOperationalRunnerTests(SimpleTestCase):
    databases = set()

    def setUp(self):
        FakeMedia.calls = 0
        FakeSequences.calls = 0

    def build(self, root, **overrides):
        defaults = {
            "audit_dir": root / "audit",
            "sqlite_path": root / "database.sqlite3",
            "media_tar_path": root / "media.tar.gz",
            "checksum_manifest_path": root / "SHA256SUMS.txt",
            "report_root": root / "reports",
            "staging_root": root / "staging",
            "media_root": root / "media",
            "connection": FakeConnection(),
            "validator_suite": FakeSuite(),
            "planner_factory": FakePlanner,
            "manifest_loader": lambda path: FakeManifest(),
            "pipeline_validator": lambda manifest: None,
            "media_migrator_class": FakeMedia,
            "sequence_manager_class": FakeSequences,
            "production": False,
        }
        defaults.update(overrides)
        return LegacyMigrationRunner(**defaults)

    def test_validation_mode_executes_no_importer_or_database_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = []
            pipeline = (
                PipelineStage("one", "Uno", importer(events, "one"), ("one",)),
            )
            report = self.build(root, pipeline=pipeline).run()
            saved = json.loads(
                (
                    root
                    / "reports"
                    / "operational-test"
                    / "migration-report.json"
                ).read_text()
            )

        self.assertEqual(events, [])
        self.assertEqual(FakeMedia.calls, 0)
        self.assertEqual(FakeSequences.calls, 0)
        self.assertEqual(report["result"], "validation_complete_without_writes")
        self.assertEqual(saved["mode"], "validation")

    def test_rejects_production_apply_without_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = self.build(
                Path(temporary),
                apply=True,
                production=True,
            )
            with self.assertRaisesRegex(
                LegacyMigrationError, "producción"
            ):
                runner.run()

    def test_rejects_allow_production_without_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(LegacyMigrationError, "sólo"):
                self.build(
                    Path(temporary),
                    allow_production=True,
                )

    def test_apply_respects_complete_pipeline_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = []
            pipeline = tuple(
                PipelineStage(key, key, importer(events, key), (key,))
                for key in ("users", "masters", "documents")
            )
            report = self.build(
                root,
                apply=True,
                pipeline=pipeline,
            ).run()

        self.assertEqual(events, ["users", "masters", "documents"])
        self.assertEqual(FakeMedia.calls, 1)
        self.assertEqual(FakeSequences.calls, 1)
        self.assertEqual(report["result"], "migration_completed")

    def test_failure_stops_dependents_media_and_sequences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = []
            pipeline = (
                PipelineStage("one", "Uno", importer(events, "one"), ("one",)),
                PipelineStage(
                    "two", "Dos", importer(events, "two", fail=True), ("two",)
                ),
                PipelineStage(
                    "three", "Tres", importer(events, "three"), ("three",)
                ),
            )
            runner = self.build(root, apply=True, pipeline=pipeline)
            with self.assertRaisesRegex(RuntimeError, "falló two"):
                runner.run()
            report = json.loads(
                (
                    root
                    / "reports"
                    / "operational-test"
                    / "migration-report.json"
                ).read_text()
            )

        self.assertEqual(events, ["one", "two"])
        self.assertEqual(FakeMedia.calls, 0)
        self.assertEqual(FakeSequences.calls, 0)
        self.assertEqual(report["stages"][-1]["status"], "rolled_back")
        self.assertEqual(report["result"], "migration_failed")

    def test_report_removes_sensitive_keys(self):
        payload = {
            "password": "hash",
            "nested": {"api_token": "secret", "safe": "value"},
        }
        self.assertEqual(
            LegacyMigrationRunner._sanitize(payload),
            {"nested": {"safe": "value"}},
        )
