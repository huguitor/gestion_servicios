# gestion/backup/importers.py
#
# Importadores: leen el formato exportado y aplican upsert por PK.
# Semántica: si el registro existe (mismo ID) → update_or_create.
#            Si el ID no existe → crea con ese ID forzado.
# Los registros que existen en BD pero NO en el backup quedan intactos.
#
# Archivos del ZIP se copian a MEDIA_ROOT con los mismos paths relativos
# que tenían al exportarlos. Si ya existen, se sobreescriben.

import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction

from clientes.models import Cliente
from productos.models import Producto, Servicio, ProductoImpuesto, ServicioImpuesto
from presupuestos.models import Presupuesto, PresupuestoItem, PresupuestoAdjunto
from remitos.models import Remito, ItemRemito, RemitoAdjunto
from configuracion.models import ConfiguracionGlobal


@dataclass
class RestoreSummary:
    """Resultado de una restauración para mostrarle al usuario."""
    tipo: str
    creados: int = 0
    actualizados: int = 0
    archivos_extraidos: int = 0
    detalle: dict[str, Any] | None = None

    def as_dict(self) -> dict:
        return {
            'tipo': self.tipo,
            'creados': self.creados,
            'actualizados': self.actualizados,
            'archivos_extraidos': self.archivos_extraidos,
            'detalle': self.detalle or {},
        }


class RestoreError(Exception):
    """Error de restauración con mensaje legible para el cliente."""


def _validate_tipo(payload: dict, esperado: str) -> None:
    """Verifica que el JSON sea del tipo correcto."""
    tipo = payload.get('tipo')
    if tipo != esperado:
        raise RestoreError(
            f"El archivo es de tipo '{tipo}', se esperaba '{esperado}'. "
            f"Asegurate de subir un backup compatible."
        )


def _read_zip_data_json(file_bytes: bytes) -> tuple[dict, zipfile.ZipFile]:
    """Abre el ZIP, lee data.json y devuelve (payload, zf abierto)."""
    zf = zipfile.ZipFile(io.BytesIO(file_bytes), 'r')
    try:
        data_json = zf.read('data.json')
    except KeyError:
        zf.close()
        raise RestoreError("El ZIP no contiene data.json — no es un backup válido.")
    payload = json.loads(data_json)
    return payload, zf


def _extract_media(zf: zipfile.ZipFile) -> int:
    """
    Extrae todos los archivos que empiezan con 'media/' al MEDIA_ROOT.
    Devuelve la cantidad de archivos extraídos.
    """
    count = 0
    for name in zf.namelist():
        if not name.startswith('media/') or name.endswith('/'):
            continue
        rel = name[len('media/'):]
        target = os.path.join(settings.MEDIA_ROOT, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(name) as src, open(target, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        count += 1
    return count


def _upsert_records(model, records: list[dict], skip_fields: set[str] = frozenset()) -> tuple[int, int]:
    """
    Por cada registro: si existe por PK → update. Si no → crea con ese ID.
    Devuelve (creados, actualizados).
    """
    pk_name = model._meta.pk.name
    creados = 0
    actualizados = 0

    # Mapeo: nombre del modelo → nombre del atributo de FK (cliente → cliente_id, etc.)
    fk_attnames = {
        f.name: f.attname for f in model._meta.fields if f.is_relation
    }

    for rec in records:
        pk_value = rec.get(pk_name)
        if pk_value is None:
            continue

        # Normalizar: si el dump tiene 'cliente' = id, mapearlo a 'cliente_id'.
        # (En realidad nuestro exporter ya guarda con _id, pero por las dudas
        # aceptamos ambos.)
        normalized = {}
        for key, value in rec.items():
            if key in skip_fields:
                continue
            if key in fk_attnames and key != fk_attnames[key]:
                normalized[fk_attnames[key]] = value
            else:
                normalized[key] = value

        defaults = {k: v for k, v in normalized.items() if k != pk_name}

        _, created = model.objects.update_or_create(
            **{pk_name: pk_value},
            defaults=defaults,
        )
        if created:
            creados += 1
        else:
            actualizados += 1

    return creados, actualizados


# ---------------------------------------------------------------------------
# Restauradores granulares
# ---------------------------------------------------------------------------

@transaction.atomic
def restore_clientes(file_bytes: bytes) -> RestoreSummary:
    """Acepta JSON directo (no ZIP)."""
    try:
        payload = json.loads(file_bytes)
    except json.JSONDecodeError as e:
        raise RestoreError(f"JSON inválido: {e}")
    _validate_tipo(payload, 'clientes')
    creados, actualizados = _upsert_records(Cliente, payload.get('registros', []))
    return RestoreSummary('clientes', creados=creados, actualizados=actualizados)


@transaction.atomic
def restore_productos(file_bytes: bytes) -> RestoreSummary:
    """ZIP con data.json + media/."""
    payload, zf = _read_zip_data_json(file_bytes)
    try:
        _validate_tipo(payload, 'productos')
        creados, actualizados = _upsert_records(Producto, payload.get('registros', []))
        # Through M2M: borrar los que están y meter los del backup
        # (los registros tienen producto_id y impuesto_id, no FK lookups).
        prod_imp = payload.get('productoimpuesto_set', [])
        ProductoImpuesto.objects.filter(
            producto_id__in=[r.get('producto_id') for r in prod_imp if r.get('producto_id')]
        ).delete()
        for rec in prod_imp:
            rec.pop('id', None)
            ProductoImpuesto.objects.create(**rec)
        extracted = _extract_media(zf)
    finally:
        zf.close()
    return RestoreSummary(
        'productos',
        creados=creados,
        actualizados=actualizados,
        archivos_extraidos=extracted,
        detalle={'productoimpuesto_set': len(prod_imp)},
    )


@transaction.atomic
def restore_servicios(file_bytes: bytes) -> RestoreSummary:
    payload, zf = _read_zip_data_json(file_bytes)
    try:
        _validate_tipo(payload, 'servicios')
        creados, actualizados = _upsert_records(Servicio, payload.get('registros', []))
        serv_imp = payload.get('servicioimpuesto_set', [])
        ServicioImpuesto.objects.filter(
            servicio_id__in=[r.get('servicio_id') for r in serv_imp if r.get('servicio_id')]
        ).delete()
        for rec in serv_imp:
            rec.pop('id', None)
            ServicioImpuesto.objects.create(**rec)
        extracted = _extract_media(zf)
    finally:
        zf.close()
    return RestoreSummary(
        'servicios',
        creados=creados,
        actualizados=actualizados,
        archivos_extraidos=extracted,
        detalle={'servicioimpuesto_set': len(serv_imp)},
    )


@transaction.atomic
def restore_presupuestos(file_bytes: bytes) -> RestoreSummary:
    payload, zf = _read_zip_data_json(file_bytes)
    try:
        _validate_tipo(payload, 'presupuestos')
        # 1. Presupuestos
        creados, actualizados = _upsert_records(Presupuesto, payload.get('registros', []))
        # 2. Items: borramos los items existentes de los presupuestos restaurados
        #    y recreamos. Más seguro que upsert por id porque los items se
        #    eliminan al editar un presupuesto desde la UI normalmente.
        items = payload.get('items', [])
        presupuesto_ids = {r.get('presupuesto_id') for r in items if r.get('presupuesto_id')}
        PresupuestoItem.objects.filter(presupuesto_id__in=presupuesto_ids).delete()
        for rec in items:
            rec.pop('id', None)
            PresupuestoItem.objects.create(**rec)
        # 3. Adjuntos: upsert por ID
        adjuntos = payload.get('adjuntos', [])
        adj_creados, adj_actualizados = _upsert_records(PresupuestoAdjunto, adjuntos)
        # 4. Archivos
        extracted = _extract_media(zf)
    finally:
        zf.close()
    return RestoreSummary(
        'presupuestos',
        creados=creados,
        actualizados=actualizados,
        archivos_extraidos=extracted,
        detalle={
            'items': len(items),
            'adjuntos_creados': adj_creados,
            'adjuntos_actualizados': adj_actualizados,
        },
    )


@transaction.atomic
def restore_remitos(file_bytes: bytes) -> RestoreSummary:
    payload, zf = _read_zip_data_json(file_bytes)
    try:
        _validate_tipo(payload, 'remitos')
        creados, actualizados = _upsert_records(Remito, payload.get('registros', []))
        items = payload.get('items', [])
        remito_ids = {r.get('remito_id') for r in items if r.get('remito_id')}
        ItemRemito.objects.filter(remito_id__in=remito_ids).delete()
        for rec in items:
            rec.pop('id', None)
            ItemRemito.objects.create(**rec)
        adjuntos = payload.get('adjuntos', [])
        adj_creados, adj_actualizados = _upsert_records(RemitoAdjunto, adjuntos)
        extracted = _extract_media(zf)
    finally:
        zf.close()
    return RestoreSummary(
        'remitos',
        creados=creados,
        actualizados=actualizados,
        archivos_extraidos=extracted,
        detalle={
            'items': len(items),
            'adjuntos_creados': adj_creados,
            'adjuntos_actualizados': adj_actualizados,
        },
    )


@transaction.atomic
def restore_configuracion(file_bytes: bytes) -> RestoreSummary:
    payload, zf = _read_zip_data_json(file_bytes)
    try:
        _validate_tipo(payload, 'configuracion')
        creados, actualizados = _upsert_records(ConfiguracionGlobal, payload.get('registros', []))
        extracted = _extract_media(zf)
    finally:
        zf.close()
    return RestoreSummary(
        'configuracion',
        creados=creados,
        actualizados=actualizados,
        archivos_extraidos=extracted,
    )


# ---------------------------------------------------------------------------
# Restaurador "todo" — procesa el ZIP master
# ---------------------------------------------------------------------------

IMPORTERS_BY_TIPO = {
    'clientes': restore_clientes,
    'productos': restore_productos,
    'servicios': restore_servicios,
    'presupuestos': restore_presupuestos,
    'remitos': restore_remitos,
    'configuracion': restore_configuracion,
}


def restore_todo(file_bytes: bytes) -> list[RestoreSummary]:
    """
    Procesa un ZIP master generado por export_todo.
    Cada archivo interno (backup_<tipo>_*.{json,zip}) se procesa con su
    restaurador específico. El orden de procesamiento es estable: primero
    los catálogos (clientes, productos, servicios), después los que dependen
    (presupuestos, remitos), por último configuración.
    """
    zf = zipfile.ZipFile(io.BytesIO(file_bytes), 'r')
    try:
        # Detectar manifiesto para validar
        try:
            manifest = json.loads(zf.read('manifest.json'))
            if manifest.get('tipo') != 'todo':
                raise RestoreError(
                    f"El ZIP master tiene manifest.tipo='{manifest.get('tipo')}', se esperaba 'todo'."
                )
        except KeyError:
            raise RestoreError("El ZIP no tiene manifest.json — no es un backup 'todo' válido.")

        # Orden de restauración: catálogos antes de los que dependen.
        orden = ['clientes', 'productos', 'servicios', 'configuracion', 'presupuestos', 'remitos']
        archivos_por_tipo: dict[str, str] = {}
        for name in zf.namelist():
            for tipo in orden:
                if name.startswith(f'backup_{tipo}_') and (
                    name.endswith('.json') or name.endswith('.zip')
                ):
                    archivos_por_tipo[tipo] = name

        summaries: list[RestoreSummary] = []
        for tipo in orden:
            if tipo not in archivos_por_tipo:
                continue
            inner_bytes = zf.read(archivos_por_tipo[tipo])
            summaries.append(IMPORTERS_BY_TIPO[tipo](inner_bytes))
        return summaries
    finally:
        zf.close()
