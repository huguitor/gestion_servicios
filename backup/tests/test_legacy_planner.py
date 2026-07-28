import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from django.test import SimpleTestCase

from backup.legacy.manifest import LegacyManifest
from backup.legacy.planner import LegacyPlanner, PlannerError
from backup.legacy.validators import ValidationResult
from backup.tests.legacy_fixtures import write_audit_dir


class LegacyPlannerTests(SimpleTestCase):
    databases = set()

    def test_generates_exact_report_set_without_apply_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = LegacyManifest.load(write_audit_dir(root / "audit"))
            planner = LegacyPlanner(
                root / "plans",
                clock=lambda: datetime(2026, 7, 28, tzinfo=timezone.utc),
            )

            result = planner.generate(
                manifest,
                [ValidationResult("preflight", "ok", "Correcto")],
            )

            output_dir = Path(result["output_dir"])
            self.assertEqual(
                {path.name for path in output_dir.iterdir()},
                set(LegacyPlanner.REPORTS),
            )
            plan = json.loads((output_dir / "plan.json").read_text())
            self.assertFalse(plan["writes_business_data"])
            self.assertEqual(plan["mode"], "validation")
            self.assertEqual(len(plan["stages"]), 19)
            self.assertTrue(plan["execution_pipeline"])
            self.assertTrue(plan["sequence_plan"])

    def test_models_report_contains_defaults_and_source_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit_dir = write_audit_dir(root / "audit")
            schema_path = audit_dir / "schema.json"
            schema = json.loads(schema_path.read_text())
            schema["tables"]["clientes_cliente"]["count"] = 5
            schema_path.write_text(json.dumps(schema))
            manifest = LegacyManifest.load(audit_dir)

            result = LegacyPlanner(root / "plans").generate(manifest, [])

            models = result["reports"]["models.json"]["models"]
            cliente = next(
                item for item in models if item["source_table"] == "clientes_cliente"
            )
            self.assertEqual(cliente["source_count"], 5)
            self.assertEqual(cliente["defaults"]["plazo_cobro_dias"], 0)

    def test_does_not_overwrite_existing_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = LegacyManifest.load(write_audit_dir(root / "audit"))
            planner = LegacyPlanner(root / "plans")
            planner.generate(manifest, [])

            with self.assertRaises(PlannerError):
                planner.generate(manifest, [])
