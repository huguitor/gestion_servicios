"""Ejecuta el pipeline operativo de migración SQLite legacy."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from backup.legacy.manifest import LegacyManifest
from backup.legacy.runner import LegacyMigrationRunner


class Command(BaseCommand):
    help = (
        "Valida o aplica la migración SQLite legacy. Sin --apply nunca "
        "escribe datos de negocio."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sqlite", required=True, help="Ruta al SQLite legacy.")
        parser.add_argument(
            "--manifest",
            required=True,
            help="Directorio de la auditoría aprobada.",
        )
        parser.add_argument(
            "--media-tar",
            required=True,
            help="Ruta al archivo media.tar.gz legacy.",
        )
        parser.add_argument(
            "--checksums",
            required=True,
            help="Ruta al archivo SHA256SUMS.txt aprobado.",
        )
        parser.add_argument(
            "--reports",
            default=str(Path(settings.DATA_DIR_ABS) / "legacy-import"),
            help="Directorio raíz para planes e informes.",
        )
        parser.add_argument(
            "--staging",
            default=str(Path(settings.DATA_DIR_ABS) / "legacy-staging"),
            help="Directorio temporal de staging.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Tamaño de lote de lectura e inserción.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Habilita explícitamente las escrituras de migración.",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Confirma explícitamente una ejecución --apply en producción.",
        )
        parser.add_argument(
            "--keep-staging",
            action="store_true",
            help="Conserva staging para diagnóstico; no usar normalmente.",
        )

    def handle(self, *args, **options):
        if options["batch_size"] < 1:
            raise CommandError("--batch-size debe ser mayor que cero.")
        if options["allow_production"] and not options["apply"]:
            raise CommandError("--allow-production requiere --apply.")

        try:
            manifest = LegacyManifest.load(options["manifest"])
        except Exception as exc:
            raise CommandError(f"Manifest de auditoría inválido: {exc}") from exc

        mode = "APPLY" if options["apply"] else "VALIDACIÓN SIN ESCRITURAS"
        destination = connection.settings_dict
        self.stdout.write(f"Modo......................{mode}")
        self.stdout.write(
            f"SQLite....................{Path(options['sqlite']).resolve()}"
        )
        self.stdout.write(
            "PostgreSQL................"
            f"{destination.get('HOST') or 'local'}/"
            f"{destination.get('NAME') or ''}"
        )
        self.stdout.write(
            f"Tablas planificadas.......{len(manifest.imported_mappings)}"
        )
        self.stdout.write(
            "Registros estimados......."
            f"{sum(manifest.source_count(m.source_table) for m in manifest.imported_mappings)}"
        )

        try:
            report = LegacyMigrationRunner(
                audit_dir=options["manifest"],
                sqlite_path=options["sqlite"],
                media_tar_path=options["media_tar"],
                checksum_manifest_path=options["checksums"],
                report_root=options["reports"],
                staging_root=options["staging"],
                batch_size=options["batch_size"],
                apply=options["apply"],
                allow_production=options["allow_production"],
                keep_staging=options["keep_staging"],
            ).run()
        except Exception as exc:
            self.stderr.write(self.style.ERROR("MIGRACIÓN FALLIDA"))
            raise CommandError(str(exc)) from exc

        if report["result"] == "migration_completed":
            label = "MIGRACIÓN COMPLETADA"
        else:
            label = "VALIDACIÓN COMPLETA SIN ESCRITURAS"
        self.stdout.write(self.style.SUCCESS(label))
        self.stdout.write(f"Run.......................{report['run_id']}")
        self.stdout.write(
            f"Informes..................{report.get('report_dir', options['reports'])}"
        )
