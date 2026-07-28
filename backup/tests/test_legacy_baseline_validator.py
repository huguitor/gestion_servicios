from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import TestCase
from types import SimpleNamespace

from backup.legacy.validators import (
    BusinessTablesEmptyValidator,
    PreflightError,
    ValidationContext,
)
from clientes.models import Cliente
from personal.models import RolPersonal


class LegacyBaselineValidatorTests(TestCase):
    def context(self, manifest=None):
        return ValidationContext(
            manifest=manifest,
            sqlite_path=None,
            media_tar_path=None,
            checksum_manifest_path=None,
            staging_root=None,
            media_root=None,
            connection=connection,
            postgres_tables=set(connection.introspection.table_names()),
        )

    def validate(self, manifest=None):
        return BusinessTablesEmptyValidator().validate(
            self.context(manifest)
        )

    def invalid_details(self, manifest=None):
        with self.assertRaises(PreflightError) as captured:
            self.validate(manifest)
        return captured.exception.details

    def baseline_result(self, details, table):
        return next(
            item
            for item in details["tables"]
            if item["table"] == table
        )

    def test_freshly_migrated_database_accepts_exact_baseline(self):
        result = self.validate()

        self.assertEqual(result.status, "ok")
        statuses = {
            item["table"]: item["status"]
            for item in result.details["tables"]
        }
        self.assertEqual(statuses["auth_group"], "baseline_valid")
        self.assertEqual(
            statuses["auth_group_permissions"], "baseline_valid"
        )
        self.assertEqual(
            statuses["personal_rolpersonal"], "baseline_valid"
        )

    def test_rejects_additional_group(self):
        Group.objects.bulk_create([Group(id=99, name="ADICIONAL")])

        result = self.baseline_result(
            self.invalid_details(), "auth_group"
        )

        self.assertEqual(result["status"], "baseline_invalid")
        self.assertEqual(result["additional_rows"], [{"id": 99, "name": "ADICIONAL"}])

    def test_rejects_modified_group_name(self):
        Group.objects.filter(pk=1).update(name="MODIFICADO")

        result = self.baseline_result(
            self.invalid_details(), "auth_group"
        )

        self.assertEqual(
            result["different_fields"][0]["fields"]["name"]["found"],
            "MODIFICADO",
        )

    def test_rejects_missing_group(self):
        RolPersonal.objects.filter(pk=1).delete()
        Group.objects.filter(pk=1).delete()

        result = self.baseline_result(
            self.invalid_details(), "auth_group"
        )

        self.assertEqual(result["missing_rows"][0]["id"], 1)

    def test_rejects_additional_group_permission(self):
        through = Group.permissions.through
        permission = Permission.objects.get(
            content_type__app_label="personal",
            content_type__model="empleado",
            codename="access_admin_frontend",
        )
        through.objects.bulk_create(
            [
                through(
                    id=99,
                    group_id=1,
                    permission_id=permission.pk,
                )
            ]
        )

        result = self.baseline_result(
            self.invalid_details(), "auth_group_permissions"
        )

        self.assertEqual(result["additional_rows"][0]["id"], 99)

    def test_rejects_missing_group_permission(self):
        Group.permissions.through.objects.filter(pk=1).delete()

        result = self.baseline_result(
            self.invalid_details(), "auth_group_permissions"
        )

        self.assertEqual(result["missing_rows"][0]["id"], 1)

    def test_rejects_additional_personal_role(self):
        Group.objects.bulk_create([Group(id=99, name="PERSONAL_EXTRA")])
        RolPersonal.objects.bulk_create(
            [
                RolPersonal(
                    id=99,
                    codigo="EXTRA",
                    nombre="Extra",
                    descripcion="",
                    grupo_id=99,
                    activo=True,
                    orden=99,
                )
            ]
        )

        result = self.baseline_result(
            self.invalid_details(), "personal_rolpersonal"
        )

        self.assertEqual(result["additional_rows"][0]["id"], 99)

    def test_rejects_modified_personal_role(self):
        RolPersonal.objects.filter(pk=1).update(nombre="Alterado")

        result = self.baseline_result(
            self.invalid_details(), "personal_rolpersonal"
        )

        self.assertEqual(
            result["different_fields"][0]["fields"]["nombre"]["found"],
            "Alterado",
        )

    def test_importable_business_table_with_row_is_still_rejected(self):
        Cliente.objects.bulk_create(
            [
                Cliente(
                    id=99,
                    tipo="juridica",
                    nombre="Cliente inesperado",
                )
            ]
        )

        manifest = SimpleNamespace(
            imported_mappings=(
                SimpleNamespace(target_model="clientes.Cliente"),
            )
        )
        details = self.invalid_details(manifest)

        self.assertIn(
            {
                "table": "clientes_cliente",
                "category": "import_destination",
                "status": "unexpected_data",
            },
            details["unexpected_data"],
        )

    def test_invalid_report_contains_counts_missing_additional_and_differences(self):
        Group.objects.filter(pk=1).update(name="Alterado")
        Group.objects.bulk_create([Group(id=99, name="ADICIONAL")])

        result = self.baseline_result(
            self.invalid_details(), "auth_group"
        )

        self.assertEqual(result["expected_count"], 4)
        self.assertEqual(result["found_count"], 5)
        self.assertEqual(result["missing_rows"], [])
        self.assertTrue(result["additional_rows"])
        self.assertTrue(result["different_fields"])
