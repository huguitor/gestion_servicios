"""
Servicio de creación de pedidos internos.

Las operaciones del flujo posterior a la creación pertenecen a
WorkflowService.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models.movimiento import PedidoMovimiento
from ..models.pedido import PedidoInterno
from ..models.pedido_destino import PedidoDestino
from ..models.pedido_detalle import PedidoInternoDetalle
from ..models.sector import Sector
from ..models.usuario_sector import UsuarioSector


@transaction.atomic
def crear_pedido(
    *,
    solicitante,
    sector_origen,
    detalles,
    destinos,
    prioridad=PedidoInterno.Prioridad.NORMAL,
    observaciones="",
    fecha=None,
):
    """
    Crea un pedido interno completo dentro de una transacción.

    Si falla la cabecera, un detalle, un destino o un movimiento,
    se revierte la operación completa.
    """

    _validar_creacion(
        solicitante=solicitante,
        sector_origen=sector_origen,
        detalles=detalles,
        destinos=destinos,
    )

    sector_origen_obj = _obtener_sector_activo(sector_origen)

    pedido = PedidoInterno(
        solicitante=solicitante,
        sector_origen=sector_origen_obj,
        prioridad=prioridad,
        observaciones=observaciones or "",
    )

    if fecha is not None:
        pedido.fecha = fecha

    pedido.save()

    _crear_detalles(
        pedido=pedido,
        detalles=detalles,
    )

    destinos_creados = _crear_destinos(
        pedido=pedido,
        destinos=destinos,
    )

    pedido.registrar_movimiento(
        usuario=solicitante,
        accion=PedidoMovimiento.Accion.CREADO,
        detalle=(
            f"Pedido creado desde el sector "
            f"{sector_origen_obj.codigo}."
        ),
        estado_nuevo=PedidoInterno.Estado.PENDIENTE,
    )

    # Cada destino necesita su propio instante de envío.
    # Este movimiento será el inicio del SLA enviado → leído.
    for destino in destinos_creados:
        pedido.registrar_movimiento(
            destino=destino,
            usuario=solicitante,
            accion=PedidoMovimiento.Accion.ENVIADO,
            detalle=(
                f"Pedido enviado al sector "
                f"{destino.sector_destino.codigo}."
            ),
            estado_nuevo=PedidoDestino.Estado.PENDIENTE,
            metadata={
                "sector_destino_id": destino.sector_destino_id,
            },
        )

    return pedido


def _validar_creacion(
    *,
    solicitante,
    sector_origen,
    detalles,
    destinos,
):
    if solicitante is None or not getattr(solicitante, "is_authenticated", False):
        raise ValidationError(
            "Se requiere un usuario autenticado para crear el pedido."
        )

    if sector_origen is None:
        raise ValidationError(
            "Debe indicar un sector de origen."
        )

    if not detalles:
        raise ValidationError(
            "El pedido debe tener al menos un detalle."
        )

    if not destinos:
        raise ValidationError(
            "El pedido debe tener al menos un destino."
        )

    sector_origen_obj = _obtener_sector_activo(sector_origen)

    pertenece = UsuarioSector.objects.filter(
        usuario_id=solicitante.pk,
        sector_id=sector_origen_obj.pk,
        activo=True,
    ).exists()

    if not pertenece:
        raise ValidationError({
            "sector_origen": (
                "El usuario no pertenece activamente "
                "al sector de origen."
            )
        })


def _crear_detalles(*, pedido, detalles):
    for posicion, item in enumerate(detalles, start=1):
        if not isinstance(item, dict):
            raise ValidationError(
                f"El detalle {posicion} tiene un formato inválido."
            )

        tipo = item.get("tipo")

        if not tipo:
            raise ValidationError(
                f"El detalle {posicion} no tiene un tipo válido."
            )

        cantidad = item.get("cantidad", 1)

        if cantidad in (None, ""):
            cantidad = 1

        detalle = PedidoInternoDetalle(
            pedido=pedido,
            tipo=tipo,
            producto=item.get("producto"),
            servicio=item.get("servicio"),
            descripcion=item.get("descripcion", "") or "",
            cantidad=cantidad,
            observacion=item.get("observacion", "") or "",
        )

        # Ejecuta las validaciones propias del modelo antes de insertar.
        detalle.full_clean()
        detalle.save()


def _crear_destinos(*, pedido, destinos):
    sectores = _normalizar_destinos(destinos)

    if pedido.sector_origen_id in sectores:
        raise ValidationError({
            "destinos": (
                "El sector de origen no puede agregarse como "
                "destino inicial del mismo pedido."
            )
        })

    sectores_obj = list(
        Sector.objects.filter(
            pk__in=sectores,
            activo=True,
        )
    )

    encontrados = {sector.pk for sector in sectores_obj}
    faltantes = set(sectores) - encontrados

    if faltantes:
        raise ValidationError({
            "destinos": (
                "Uno o más sectores destino no existen "
                "o se encuentran inactivos."
            )
        })

    destinos_creados = []

    for sector in sectores_obj:
        destino = PedidoDestino.objects.create(
            pedido=pedido,
            sector_destino=sector,
        )
        destinos_creados.append(destino)

    return destinos_creados


def _normalizar_destinos(destinos):
    """
    Convierte instancias o IDs de Sector en una lista única de IDs.

    Evita usar set(destinos), porque podría recibir una combinación
    de enteros e instancias y ocultar duplicados equivalentes.
    """
    sector_ids = []
    vistos = set()

    for posicion, sector in enumerate(destinos, start=1):
        sector_id = (
            sector.pk
            if isinstance(sector, Sector)
            else sector
        )

        if sector_id is None:
            raise ValidationError(
                f"El destino {posicion} no tiene un ID válido."
            )

        try:
            sector_id = int(sector_id)
        except (TypeError, ValueError):
            raise ValidationError(
                f"El destino {posicion} tiene un ID inválido."
            )

        if sector_id in vistos:
            raise ValidationError({
                "destinos": (
                    f"El sector destino con ID {sector_id} "
                    "está repetido."
                )
            })

        vistos.add(sector_id)
        sector_ids.append(sector_id)

    return sector_ids


def _obtener_sector_activo(sector):
    if isinstance(sector, Sector):
        if not sector.pk:
            raise ValidationError(
                "El sector todavía no fue guardado."
            )

        if not sector.activo:
            raise ValidationError({
                "sector": "El sector se encuentra inactivo."
            })

        return sector

    try:
        sector_id = int(sector)
    except (TypeError, ValueError):
        raise ValidationError(
            "El sector indicado no es válido."
        )

    try:
        return Sector.objects.get(
            pk=sector_id,
            activo=True,
        )
    except Sector.DoesNotExist as exc:
        raise ValidationError(
            "El sector no existe o se encuentra inactivo."
        ) from exc