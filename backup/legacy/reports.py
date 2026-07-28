"""Persistencia acotada de informes JSON del auditor legacy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_NAMES = (
    "summary",
    "schema",
    "compatibility",
    "media",
    "warnings",
)


def write_reports(output_root: str | Path, run_id: str, reports: dict[str, Any]) -> Path:
    output_dir = Path(output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    for report_name in REPORT_NAMES:
        target = output_dir / f"{report_name}.json"
        target.write_text(
            json.dumps(
                reports.get(report_name, {}),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return output_dir
