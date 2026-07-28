"""Infraestructura de staging; no extrae ni publica multimedia."""

from __future__ import annotations

import os
import hashlib
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from .media_reader import LegacyMediaReader, normalize_media_path

class StagingError(Exception):
    """El staging no es seguro o no está disponible."""


class MediaStaging:
    def __init__(self, root: str | Path, media_root: str | Path):
        self.root = Path(root).resolve()
        self.media_root = Path(media_root).resolve()

    def ensure_available(self) -> dict:
        if self.root == self.media_root or self.media_root in self.root.parents:
            raise StagingError("El staging no puede estar dentro de MEDIA_ROOT.")
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise StagingError("El staging no es un directorio.")
        try:
            descriptor, probe_name = tempfile.mkstemp(
                prefix=".legacy-staging-probe-",
                dir=self.root,
            )
            os.close(descriptor)
            Path(probe_name).unlink()
        except OSError as exc:
            raise StagingError(f"El staging no permite escritura segura: {exc}") from exc
        return {
            "root": str(self.root),
            "media_root": str(self.media_root),
            "available": True,
        }

    def stage(self, tar_path: str | Path, references: list[dict]) -> dict:
        self.ensure_available()
        if any(self.root.iterdir()):
            raise StagingError("El staging debe estar vacío antes de extraer.")
        for item in references:
            raw_path = str(item.get("path") or "").replace("\\", "/")
            pure_path = PurePosixPath(raw_path)
            if pure_path.is_absolute() or ".." in pure_path.parts:
                raise StagingError(
                    f"Referencia multimedia insegura: {raw_path}"
                )
        inspection = LegacyMediaReader(tar_path).inspect(references)
        if not inspection["ok"]:
            reasons = {
                "missing": inspection["missing_references"],
                "unsafe": inspection["unsafe_paths"],
                "symlinks": inspection["symbolic_links"],
                "hardlinks": inspection["hard_links"],
                "duplicate_paths": inspection["duplicate_media_paths"],
            }
            raise StagingError(
                "La media no es segura o tiene referencias faltantes: "
                f"{reasons}"
            )
        expected = {
            normalize_media_path(item["path"]) for item in references if item.get("path")
        }
        file_by_path = {
            item["media_path"]: item for item in inspection["files"]
        }
        staged = []
        try:
            with tarfile.open(tar_path, mode="r:gz") as archive:
                members = {
                    normalize_media_path(member.name): member
                    for member in archive.getmembers()
                    if member.isfile()
                }
                for media_path in sorted(expected):
                    member = members.get(media_path)
                    if member is None or media_path not in file_by_path:
                        raise StagingError(f"Archivo faltante: {media_path}")
                    destination = (self.root / media_path).resolve()
                    if self.root != destination and self.root not in destination.parents:
                        raise StagingError(f"Path traversal: {media_path}")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise StagingError(f"No se pudo leer: {media_path}")
                    digest = hashlib.sha256()
                    with source, destination.open("wb") as target:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            target.write(chunk)
                            digest.update(chunk)
                    expected_hash = file_by_path[media_path]["sha256"]
                    if digest.hexdigest() != expected_hash:
                        raise StagingError(
                            f"Hash inconsistente al extraer: {media_path}"
                        )
                    staged.append(
                        {
                            "media_path": media_path,
                            "staged_path": str(destination),
                            "sha256": expected_hash,
                            "size": destination.stat().st_size,
                        }
                    )
        except Exception:
            self.cleanup()
            raise
        return {"root": str(self.root), "files": staged}

    def cleanup(self) -> None:
        if self.root.is_dir():
            shutil.rmtree(self.root)
