import hashlib
import io
import json
import tarfile
from pathlib import Path

from backup.legacy.manifest import MODEL_MAPPINGS, REQUIRED_AUDIT_FILES


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_tar(path: Path, files=None) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, content in (files or {}).items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


def write_checksums(path: Path, sqlite_path: Path, media_path: Path) -> None:
    path.write_text(
        (
            f"{sha256(sqlite_path)}  origen/database.sqlite3\n"
            f"{sha256(media_path)}  origen/media.tar.gz\n"
        ),
        encoding="utf-8",
    )


def write_audit_dir(
    root: Path,
    *,
    run_id="audit-test",
    sqlite_hash=None,
    media_hash=None,
    references=None,
) -> Path:
    root.mkdir(parents=True)
    source_tables = sorted(
        {
            mapping.source_table
            for mapping in MODEL_MAPPINGS
            if mapping.source_table and mapping.source_table != "sqlite_sequence"
        }
    )
    payloads = {
        "summary.json": {
            "run_id": run_id,
            "result": "apto_para_migrar",
        },
        "schema.json": {
            "tables": {
                table: {"count": 0, "columns": [], "foreign_keys": []}
                for table in source_tables
            }
        },
        "compatibility.json": {"models": []},
        "media.json": {
            "references": references or [],
            "hashes": {
                "files": [
                    {
                        "basename": "database.sqlite3",
                        "actual_sha256": sqlite_hash,
                    },
                    {
                        "basename": "media.tar.gz",
                        "actual_sha256": media_hash,
                    },
                ]
            },
        },
        "warnings.json": {"items": []},
    }
    for filename in REQUIRED_AUDIT_FILES:
        (root / filename).write_text(
            json.dumps(payloads[filename]),
            encoding="utf-8",
        )
    return root
