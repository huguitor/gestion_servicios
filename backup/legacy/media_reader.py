"""Auditoría sin extracción del archivo de multimedia legacy."""

from __future__ import annotations

import hashlib
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath


class MediaAuditError(Exception):
    """El tar o el manifiesto no pudieron analizarse."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256_manifest(path: str | Path) -> list[dict]:
    entries = []
    with Path(path).open("r", encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or len(parts[0]) != 64:
                raise MediaAuditError(
                    f"SHA256SUMS.txt inválido en línea {line_number}"
                )
            digest, filename = parts
            filename = filename.lstrip("*")
            if any(character not in "0123456789abcdefABCDEF" for character in digest):
                raise MediaAuditError(
                    f"Hash SHA-256 inválido en línea {line_number}"
                )
            entries.append(
                {
                    "sha256": digest.lower(),
                    "path": filename,
                    "basename": PurePosixPath(filename).name,
                }
            )
    return entries


def validate_hashes(
    manifest_path: str | Path,
    input_paths: list[str | Path],
) -> dict:
    entries = parse_sha256_manifest(manifest_path)
    by_basename: dict[str, list[dict]] = {}
    for entry in entries:
        by_basename.setdefault(entry["basename"], []).append(entry)

    files = []
    all_ok = True
    for raw_path in input_paths:
        path = Path(raw_path)
        actual = sha256_file(path) if path.is_file() else None
        candidates = by_basename.get(path.name, [])
        expected = candidates[0]["sha256"] if len(candidates) == 1 else None
        status = "ok"
        if not path.is_file():
            status = "missing"
        elif not candidates:
            status = "not_listed"
        elif len(candidates) > 1:
            status = "ambiguous"
        elif actual != expected:
            status = "mismatch"
        if status != "ok":
            all_ok = False
        files.append(
            {
                "path": str(path.resolve()),
                "basename": path.name,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "status": status,
            }
        )

    supplied_names = {Path(path).name for path in input_paths}
    unused_entries = [
        entry for entry in entries if entry["basename"] not in supplied_names
    ]
    return {
        "ok": all_ok,
        "manifest_path": str(Path(manifest_path).resolve()),
        "files": files,
        "unused_manifest_entries": unused_entries,
    }


def normalize_media_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    for prefix in ("data/media/", "media/"):
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


class LegacyMediaReader:
    def __init__(self, tar_path: str | Path):
        self.tar_path = Path(tar_path).resolve()

    def inspect(self, references: list[dict]) -> dict:
        if not self.tar_path.is_file():
            raise MediaAuditError(
                f"No existe el archivo de media: {self.tar_path}"
            )

        try:
            with tarfile.open(self.tar_path, mode="r:gz") as archive:
                members = archive.getmembers()
        except (tarfile.TarError, OSError) as exc:
            raise MediaAuditError(f"media.tar.gz inválido: {exc}") from exc

        unsafe_paths = []
        symbolic_links = []
        hard_links = []
        special_entries = []
        files = []

        try:
            with tarfile.open(self.tar_path, mode="r:gz") as archive:
                for member in members:
                    pure_path = PurePosixPath(member.name)
                    if pure_path.is_absolute() or ".." in pure_path.parts:
                        unsafe_paths.append(member.name)
                    if member.issym():
                        symbolic_links.append(
                            {"path": member.name, "target": member.linkname}
                        )
                    elif member.islnk():
                        hard_links.append(
                            {"path": member.name, "target": member.linkname}
                        )
                    elif not member.isfile() and not member.isdir():
                        special_entries.append(
                            {
                                "path": member.name,
                                "type": member.type.decode(errors="replace"),
                            }
                        )
                    if member.isfile():
                        source = archive.extractfile(member)
                        digest = hashlib.sha256()
                        if source is None:
                            raise MediaAuditError(
                                f"No se pudo leer el miembro {member.name}"
                            )
                        with source:
                            for chunk in iter(
                                lambda: source.read(1024 * 1024),
                                b"",
                            ):
                                digest.update(chunk)
                        files.append(
                            {
                                "archive_path": member.name,
                                "media_path": normalize_media_path(member.name),
                                "size": member.size,
                                "sha256": digest.hexdigest(),
                            }
                        )
        except (tarfile.TarError, OSError) as exc:
            raise MediaAuditError(
                f"No se pudo leer el contenido de media.tar.gz: {exc}"
            ) from exc

        archive_paths = [item["archive_path"] for item in files]
        media_paths = [item["media_path"] for item in files]
        duplicate_archive_paths = sorted(
            path for path, count in Counter(archive_paths).items() if count > 1
        )
        duplicate_media_paths = sorted(
            path for path, count in Counter(media_paths).items() if count > 1
        )
        paths_by_digest: dict[str, list[str]] = {}
        for item in files:
            paths_by_digest.setdefault(item["sha256"], []).append(
                item["media_path"]
            )
        duplicate_contents = [
            {"sha256": digest, "paths": sorted(paths)}
            for digest, paths in sorted(paths_by_digest.items())
            if len(paths) > 1
        ]

        reference_paths = {
            normalize_media_path(item["path"]) for item in references
        }
        archived_media_paths = set(media_paths)
        missing_references = sorted(reference_paths - archived_media_paths)
        unreferenced_files = sorted(archived_media_paths - reference_paths)

        ok = not any(
            (
                unsafe_paths,
                symbolic_links,
                hard_links,
                special_entries,
                duplicate_archive_paths,
                duplicate_media_paths,
                missing_references,
            )
        )
        return {
            "ok": ok,
            "tar_path": str(self.tar_path),
            "file_count": len(files),
            "directory_count": sum(member.isdir() for member in members),
            "total_size": sum(item["size"] for item in files),
            "files": files,
            "references": references,
            "reference_count": len(references),
            "distinct_reference_count": len(reference_paths),
            "missing_references": missing_references,
            "unreferenced_files": unreferenced_files,
            "unsafe_paths": unsafe_paths,
            "symbolic_links": symbolic_links,
            "hard_links": hard_links,
            "special_entries": special_entries,
            "duplicate_archive_paths": duplicate_archive_paths,
            "duplicate_media_paths": duplicate_media_paths,
            "duplicate_contents": duplicate_contents,
        }
