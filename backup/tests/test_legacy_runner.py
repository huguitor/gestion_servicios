import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from backup.legacy.runner import LegacyInfrastructureRunner
from backup.legacy.validators import ValidationResult


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeSuite:
    def __init__(self, events):
        self.events = events

    def run(self, context):
        self.events.append("validate")
        return [ValidationResult("all", "ok", "Correcto")]


class FakePlanner:
    def __init__(self, events, output_dir):
        self.events = events
        self.output_dir = output_dir

    def generate(self, manifest, validation_results):
        self.events.append("plan")
        return {"output_dir": str(self.output_dir)}


class LegacyRunnerTests(SimpleTestCase):
    databases = set()

    def test_runner_loads_validates_plans_and_closes_connection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = []
            connection = FakeConnection()
            manifest = SimpleNamespace(run_id="audit-test")

            def load_manifest(audit_dir):
                events.append("manifest")
                return manifest

            runner = LegacyInfrastructureRunner(
                audit_dir=root / "audit",
                sqlite_path=root / "database.sqlite3",
                media_tar_path=root / "media.tar.gz",
                checksum_manifest_path=root / "SHA256SUMS.txt",
                plan_output_root=root / "plans",
                staging_root=root / "staging",
                media_root=root / "media",
                connection=connection,
                validator_suite=FakeSuite(events),
                planner=FakePlanner(events, root / "plans" / "audit-test"),
                manifest_loader=load_manifest,
            )

            result = runner.run()

        self.assertEqual(events, ["manifest", "validate", "plan"])
        self.assertEqual(result.state, "finished")
        self.assertTrue(connection.closed)

    def test_runner_aborts_and_closes_connection_on_validation_error(self):
        class FailingSuite:
            def run(self, context):
                raise RuntimeError("preflight")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            connection = FakeConnection()
            runner = LegacyInfrastructureRunner(
                audit_dir=root,
                sqlite_path=root / "database.sqlite3",
                media_tar_path=root / "media.tar.gz",
                checksum_manifest_path=root / "SHA256SUMS.txt",
                connection=connection,
                validator_suite=FailingSuite(),
                planner=FakePlanner([], root / "plan"),
                manifest_loader=lambda audit_dir: SimpleNamespace(run_id="audit-test"),
            )

            with self.assertRaisesRegex(RuntimeError, "preflight"):
                runner.run()

        self.assertEqual(runner.state, "failed")
        self.assertTrue(connection.closed)
