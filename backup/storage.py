# gestion/backup/storage.py
#
# Persiste backups en data/backups/ y expone helpers para listar/leer.

import os
from datetime import datetime
from pathlib import Path

from django.conf import settings


def backup_dir() -> Path:
    """
    Directorio de almacenamiento. settings.DATA_DIR_ABS apunta a
    /var/www/gestion_servicios/data/ (definido en sistema_general/settings.py).
    Lo creamos al vuelo si no existe.
    """
    path = Path(settings.DATA_DIR_ABS) / 'backups'
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_to_disk(filename: str, content: bytes) -> Path:
    """
    Guarda el contenido en disco. Si el nombre ya existe (timestamp colisiona),
    le agrega un sufijo numérico.
    """
    target = backup_dir() / filename
    if target.exists():
        stem, ext = os.path.splitext(filename)
        i = 1
        while True:
            target = backup_dir() / f"{stem}_{i}{ext}"
            if not target.exists():
                break
            i += 1
    target.write_bytes(content)
    return target


def list_backups() -> list[dict]:
    """
    Lista de archivos en data/backups/, ordenados por fecha desc.
    Cada item: {nombre, tamaño, tamaño_formateado, fecha, tipo}
    """
    items = []
    for f in sorted(backup_dir().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not f.is_file():
            continue
        st = f.stat()
        items.append({
            'nombre': f.name,
            'tamaño': st.st_size,
            'tamaño_formateado': _format_size(st.st_size),
            'fecha': datetime.fromtimestamp(st.st_mtime).isoformat(),
            'tipo': _detect_tipo(f.name),
        })
    return items


def get_backup_path(filename: str) -> Path | None:
    """
    Devuelve la ruta absoluta de un backup. None si no existe o si el nombre
    intenta escapar del directorio (defensa contra path traversal).
    """
    target = (backup_dir() / filename).resolve()
    try:
        target.relative_to(backup_dir().resolve())
    except ValueError:
        return None
    if not target.exists() or not target.is_file():
        return None
    return target


def delete_backup(filename: str) -> bool:
    """Borra un backup. Devuelve True si se borró."""
    path = get_backup_path(filename)
    if path is None:
        return False
    path.unlink()
    return True


def _format_size(size: int) -> str:
    units = ['B', 'KB', 'MB', 'GB']
    s = float(size)
    i = 0
    while s >= 1024 and i < len(units) - 1:
        s /= 1024
        i += 1
    return f"{s:.2f} {units[i]}"


def _detect_tipo(filename: str) -> str:
    """Extrae el tipo del nombre: backup_<tipo>_YYYYMMDD_HHMMSS.<ext>"""
    if not filename.startswith('backup_'):
        return 'desconocido'
    parts = filename[len('backup_'):].split('_')
    if not parts:
        return 'desconocido'
    return parts[0]
