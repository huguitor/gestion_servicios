# gestion/backup/exporters.py
#
# Exportadores granulares. Cada uno devuelve:
#   - bytes del archivo (JSON o ZIP)
#   - nombre sugerido con timestamp (backup_<tipo>_YYYYMMDD_HHMMSS.<ext>)
#   - content-type
#
# Diseño: round-trip seguro. Para cada modelo dumpeamos los IDs originales,
# todos los campos editables, y los timestamps. El importador hace upsert
# por PK. Los FK quedan como IDs.

import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.db.models import Model

# Modelos
from clientes.models import Cliente
from productos.models import Producto, Servicio, ProductoImpuesto, ServicioImpuesto
from presupuestos.models import Presupuesto, PresupuestoItem, PresupuestoAdjunto
from remitos.models import Remito, ItemRemito, RemitoAdjunto
from configuracion.models import ConfiguracionGlobal


@dataclass
class BackupResult:
    """Resultado de una exportación."""
    filename: str
    content_type: str
    data: bytes


def _ts() -> str:
    """Timestamp para nombres de archivo."""
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _json_default(obj):
    """Serializa Decimal y datetime sin perder precisión."""
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Tipo no serializable: {type(obj)}")


def _model_to_dict(instance: Model, file_fields: Iterable[str] = ()) -> dict:
    """
    Convierte un modelo a dict serializable.

    - FK → su _id (entero plano)
    - File/Image (declarado en file_fields) → string del .name (path relativo
      dentro de MEDIA_ROOT) o None si está vacío. Un FieldFile vacío es falsy
      pero no None — sin este chequeo el JSON dump explota.
    - Decimal/datetime → str (via _json_default).
    """
    file_fields_set = set(file_fields)
    data = {}
    for field in instance._meta.fields:
        name = field.name
        value = getattr(instance, name)
        if field.is_relation:
            data[name] = getattr(instance, field.attname)
        elif name in file_fields_set:
            data[name] = value.name if value else None
        else:
            data[name] = value
    return data


def _dump_model(queryset, file_fields: Iterable[str] = ()) -> list[dict]:
    """Dump completo de un queryset."""
    return [_model_to_dict(obj, file_fields=file_fields) for obj in queryset]


def _add_media_files(zf: zipfile.ZipFile, paths: Iterable[str]) -> None:
    """
    Agrega archivos del MEDIA_ROOT al ZIP preservando paths relativos.
    Ignora silenciosamente los que faltan (caso normal: campo file vacío).
    """
    seen = set()
    for rel_path in paths:
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)
        full = os.path.join(settings.MEDIA_ROOT, rel_path)
        if os.path.exists(full):
            zf.write(full, arcname=f"media/{rel_path}")


def _build_json_payload(tipo: str, records: list[dict], extras: dict | None = None) -> bytes:
    """
    Envuelve los registros en un payload con metadata para validar al restaurar.
    """
    payload = {
        'tipo': tipo,
        'generado': datetime.now().isoformat(),
        'version': 1,
        'registros': records,
    }
    if extras:
        payload.update(extras)
    return json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2).encode('utf-8')


# ---------------------------------------------------------------------------
# Exportadores granulares
# ---------------------------------------------------------------------------

def export_clientes() -> BackupResult:
    data = _build_json_payload('clientes', _dump_model(Cliente.objects.all()))
    return BackupResult(f'backup_clientes_{_ts()}.json', 'application/json', data)


def export_productos() -> BackupResult:
    # Productos = Productos + ProductoImpuesto (through M2M) + fotos + planos.
    productos = _dump_model(
        Producto.objects.all(),
        file_fields=('foto', 'plano'),
    )
    impuestos = _dump_model(ProductoImpuesto.objects.all())
    json_payload = _build_json_payload(
        'productos',
        productos,
        extras={'productoimpuesto_set': impuestos},
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json_payload)
        # Recoger paths de foto y plano para incluir como archivos.
        paths = []
        for p in Producto.objects.exclude(foto=''):
            if p.foto:
                paths.append(p.foto.name)
        for p in Producto.objects.exclude(plano=''):
            if p.plano:
                paths.append(p.plano.name)
        _add_media_files(zf, paths)

    return BackupResult(f'backup_productos_{_ts()}.zip', 'application/zip', buf.getvalue())


def export_servicios() -> BackupResult:
    servicios = _dump_model(
        Servicio.objects.all(),
        file_fields=('imagen', 'adjunto'),
    )
    impuestos = _dump_model(ServicioImpuesto.objects.all())
    json_payload = _build_json_payload(
        'servicios',
        servicios,
        extras={'servicioimpuesto_set': impuestos},
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json_payload)
        paths = []
        for s in Servicio.objects.all():
            if s.imagen:
                paths.append(s.imagen.name)
            if s.adjunto:
                paths.append(s.adjunto.name)
        _add_media_files(zf, paths)

    return BackupResult(f'backup_servicios_{_ts()}.zip', 'application/zip', buf.getvalue())


def export_presupuestos() -> BackupResult:
    presupuestos = _dump_model(Presupuesto.objects.all())
    items = _dump_model(PresupuestoItem.objects.all())
    adjuntos = _dump_model(
        PresupuestoAdjunto.objects.all(),
        file_fields=('archivo',),
    )
    json_payload = _build_json_payload(
        'presupuestos',
        presupuestos,
        extras={'items': items, 'adjuntos': adjuntos},
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json_payload)
        paths = [a.archivo.name for a in PresupuestoAdjunto.objects.all() if a.archivo]
        _add_media_files(zf, paths)

    return BackupResult(f'backup_presupuestos_{_ts()}.zip', 'application/zip', buf.getvalue())


def export_remitos() -> BackupResult:
    remitos = _dump_model(Remito.objects.all())
    items = _dump_model(ItemRemito.objects.all())
    adjuntos = _dump_model(
        RemitoAdjunto.objects.all(),
        file_fields=('archivo',),
    )
    json_payload = _build_json_payload(
        'remitos',
        remitos,
        extras={'items': items, 'adjuntos': adjuntos},
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json_payload)
        paths = [a.archivo.name for a in RemitoAdjunto.objects.all() if a.archivo]
        _add_media_files(zf, paths)

    return BackupResult(f'backup_remitos_{_ts()}.zip', 'application/zip', buf.getvalue())


def export_configuracion() -> BackupResult:
    configs = _dump_model(
        ConfiguracionGlobal.objects.all(),
        file_fields=(
            'logo_principal', 'logo_favicon', 'logo_tkinter',
            'imagen_publicitaria_1', 'imagen_publicitaria_2', 'imagen_publicitaria_3',
        ),
    )
    json_payload = _build_json_payload('configuracion', configs)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json_payload)
        paths = []
        for c in ConfiguracionGlobal.objects.all():
            for f in (
                'logo_principal', 'logo_favicon', 'logo_tkinter',
                'imagen_publicitaria_1', 'imagen_publicitaria_2', 'imagen_publicitaria_3',
            ):
                file_field = getattr(c, f)
                if file_field:
                    paths.append(file_field.name)
        _add_media_files(zf, paths)

    return BackupResult(f'backup_configuracion_{_ts()}.zip', 'application/zip', buf.getvalue())


def export_media() -> BackupResult:
    """Carpeta media/ completa. Pueden ser muchos MB."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(settings.MEDIA_ROOT):
            for fname in files:
                full = os.path.join(root, fname)
                arc = os.path.relpath(full, settings.MEDIA_ROOT)
                zf.write(full, arcname=f"media/{arc}")
    return BackupResult(f'backup_media_{_ts()}.zip', 'application/zip', buf.getvalue())


def export_database() -> BackupResult:
    """
    Copia consistente del archivo SQLite usando sqlite3 .backup API.
    Esto sí es seguro mientras Django escribe — bloquea brevemente.
    """
    import sqlite3
    import tempfile
    db_path = settings.DATABASES['default']['NAME']
    # Hacer una copia consistente a archivo temporal.
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        tmp_path = tmp.name
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        with open(tmp_path, 'rb') as f:
            data = f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return BackupResult(
        f'backup_database_{_ts()}.db',
        'application/octet-stream',
        data,
    )


# ---------------------------------------------------------------------------
# Backup "todo" — agrupa todos los anteriores en un solo ZIP
# ---------------------------------------------------------------------------

# Mapeo: clave seleccionable en frontend → función exportadora
EXPORTERS = {
    'clientes': export_clientes,
    'productos': export_productos,
    'servicios': export_servicios,
    'presupuestos': export_presupuestos,
    'remitos': export_remitos,
    'configuracion': export_configuracion,
    'media': export_media,
    'database': export_database,
}


def export_todo(items: list[str] | None = None) -> BackupResult:
    """
    Backup combinado. Si `items` viene, sólo incluye esos. Si no, incluye todos.
    Cada exportador genera su propio archivo y se mete en el ZIP master.
    """
    seleccion = items if items else list(EXPORTERS.keys())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as master:
        for key in seleccion:
            if key not in EXPORTERS:
                continue
            result = EXPORTERS[key]()
            master.writestr(result.filename, result.data)
        # Manifiesto para que el importador sepa qué hay dentro.
        manifest = {
            'tipo': 'todo',
            'generado': datetime.now().isoformat(),
            'version': 1,
            'incluye': seleccion,
        }
        master.writestr(
            'manifest.json',
            json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'),
        )

    return BackupResult(f'backup_todo_{_ts()}.zip', 'application/zip', buf.getvalue())
