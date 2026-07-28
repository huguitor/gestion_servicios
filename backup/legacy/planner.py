"""Generador determinista de artefactos; no consulta ni escribe en BD."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import STAGES
from .sequences import SequencePlanner


class PlannerError(Exception):
    """El plan no pudo generarse de forma segura."""


class LegacyPlanner:
    REPORTS = ("plan.json", "models.json", "validation.json", "warnings.json")

    def __init__(self, output_root: str | Path, sequence_planner=None, clock=None):
        self.output_root = Path(output_root)
        self.sequence_planner = sequence_planner or SequencePlanner()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def generate(
        self,
        manifest,
        validation_results,
        *,
        mode: str = "validation",
    ) -> dict[str, Any]:
        output_dir = self.output_root / manifest.run_id
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise PlannerError(
                f"Ya existe un plan para run-id {manifest.run_id}."
            ) from exc

        models = []
        for mapping in manifest.mappings:
            item = mapping.as_dict()
            item["source_count"] = manifest.source_count(mapping.source_table)
            models.append(item)

        stages = []
        for stage in STAGES:
            stage_models = [
                {
                    "source_table": mapping.source_table,
                    "target_model": mapping.target_model,
                    "action": mapping.action,
                    "source_count": manifest.source_count(mapping.source_table),
                }
                for mapping in manifest.mappings
                if mapping.stage == stage.number
            ]
            stages.append({**stage.as_dict(), "models": stage_models})

        # El runner y el artefacto de planificación comparten exactamente la
        # misma fuente de verdad. La importación nunca deriva un orden paralelo.
        from .pipeline import PIPELINE

        execution_pipeline = [
            {
                "position": position,
                "key": stage.key,
                "label": stage.label,
                "source_tables": list(stage.source_tables),
            }
            for position, stage in enumerate(PIPELINE, start=1)
        ]

        validation_payload = {
            "status": "ok",
            "results": [result.as_dict() for result in validation_results],
        }
        validation_warnings = [
            result.as_dict()
            for result in validation_results
            if result.status == "warning"
        ]
        audit_warnings = manifest.warnings.get("items", [])
        warnings_payload = {
            "items": [*audit_warnings, *validation_warnings],
        }
        plan = {
            "version": 1,
            "generated_at": self.clock().isoformat(),
            "audit_run_id": manifest.run_id,
            "mode": mode,
            "writes_business_data": mode == "apply",
            "stages": stages,
            "execution_pipeline": execution_pipeline,
            "sequence_plan": self.sequence_planner.build(manifest),
        }

        payloads = {
            "plan.json": plan,
            "models.json": {
                "audit_run_id": manifest.run_id,
                "models": models,
            },
            "validation.json": validation_payload,
            "warnings.json": warnings_payload,
        }
        try:
            for filename, payload in payloads.items():
                self._write_json(output_dir / filename, payload)
        except (OSError, TypeError, ValueError) as exc:
            raise PlannerError(f"No se pudieron escribir los planes: {exc}") from exc
        return {
            "output_dir": str(output_dir),
            "reports": payloads,
        }

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
