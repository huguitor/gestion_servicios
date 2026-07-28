"""Ejecuta la auditoría de una instalación SQLite legacy."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from backup.legacy import LegacyAudit, LegacyAuditError


class Command(BaseCommand):
    help = (
        "Audita una base SQLite legacy y su media sin escribir datos de negocio."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite",
            required=True,
            help="Ruta a database.sqlite3.",
        )
        parser.add_argument(
            "--media-tar",
            required=True,
            help="Ruta a media.tar.gz.",
        )
        parser.add_argument(
            "--checksums",
            required=True,
            help="Ruta a SHA256SUMS.txt.",
        )
        parser.add_argument(
            "--output-root",
            default=str(Path(settings.DATA_DIR_ABS) / "legacy-audit"),
            help="Directorio raíz de informes.",
        )
        parser.add_argument(
            "--run-id",
            help="Identificador opcional y único de ejecución.",
        )

    def handle(self, *args, **options):
        try:
            result = LegacyAudit(
                sqlite_path=options["sqlite"],
                media_tar_path=options["media_tar"],
                checksum_manifest_path=options["checksums"],
                output_root=options["output_root"],
                run_id=options["run_id"],
            ).run()
        except LegacyAuditError as exc:
            raise CommandError(str(exc)) from exc
        except FileExistsError as exc:
            raise CommandError(
                "El run-id ya existe; elegí otro para no sobrescribir informes."
            ) from exc

        self._line("SQLite", "OK" if result["summary"]["sqlite_ok"] else "ERROR")
        self._line("Hashes", "OK" if result["summary"]["hashes_ok"] else "ERROR")
        self._line("Media", "OK" if result["summary"]["media_ok"] else "ERROR")

        labels = {
            "clientes.Cliente": "Cliente",
            "productos.Producto": "Producto",
            "productos.Servicio": "Servicio",
            "presupuestos.Presupuesto": "Presupuesto",
            "remitos.Remito": "Remito",
        }
        status_labels = {
            "compatible": "Compatible",
            "requires_adaptation": "Requiere adaptación",
            "incompatible": "Incompatible",
        }
        compatibility_by_model = {
            item["model"]: item
            for item in result["compatibility"]["models"]
        }
        for model_label, display_name in labels.items():
            item = compatibility_by_model.get(model_label)
            status = status_labels[item["status"]] if item else "No encontrado"
            self._line(f"Modelo {display_name}", status)

        final = (
            "APTO PARA MIGRAR"
            if result["summary"]["result"] == "apto_para_migrar"
            else "REQUIERE CORRECCIONES"
        )
        self._line("Resultado", final)
        self.stdout.write(f"Informes..................{result['output_dir']}")

    def _line(self, label: str, value: str):
        dots = "." * max(1, 28 - len(label))
        self.stdout.write(f"{label}{dots}{value}")
