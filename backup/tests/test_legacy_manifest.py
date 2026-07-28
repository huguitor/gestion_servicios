import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from backup.legacy.manifest import LegacyManifest, ManifestError, MODEL_MAPPINGS
from backup.legacy.schema import ACTION_EXCLUDE, ACTION_GENERATED, ACTION_IMPORT
from backup.tests.legacy_fixtures import write_audit_dir


class LegacyManifestTests(SimpleTestCase):
    databases = set()

    def test_loads_approved_audit_and_covers_all_source_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            audit_dir = write_audit_dir(Path(temporary) / "audit")

            manifest = LegacyManifest.load(audit_dir)

        source_tables = set(manifest.schema["tables"])
        mapped_tables = {
            mapping.source_table
            for mapping in manifest.mappings
            if mapping.source_table
        }
        self.assertEqual(source_tables - mapped_tables, set())
        self.assertEqual(manifest.run_id, "audit-test")

    def test_definitive_policies_include_import_exclude_and_generated(self):
        actions = {mapping.action for mapping in MODEL_MAPPINGS}

        self.assertTrue({ACTION_IMPORT, ACTION_EXCLUDE, ACTION_GENERATED} <= actions)
        cliente = next(
            mapping
            for mapping in MODEL_MAPPINGS
            if mapping.source_table == "clientes_cliente"
        )
        self.assertEqual(cliente.defaults, {"plazo_cobro_dias": 0})
        self.assertEqual(cliente.id_policy, "preserve")

    def test_rejects_unapproved_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            audit_dir = write_audit_dir(Path(temporary) / "audit")
            summary_path = audit_dir / "summary.json"
            summary = json.loads(summary_path.read_text())
            summary["result"] = "requiere_correcciones"
            summary_path.write_text(json.dumps(summary))

            with self.assertRaises(ManifestError):
                LegacyManifest.load(audit_dir)
