# gestion/backend/pedidos_internos/services/pedido_service.py
"""
Lógica de negocio del flujo humano de pedidos internos (Sprint 1).

Mantiene los viewsets/admin delgados: toda creación o transición de
estado pasa por acá y registra el movimiento correspondiente.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import (
    PedidoInterno,
    PedidoInternoDetalle,
    PedidoDestino,
    Sector,
)


@transaction.atomic
def crear_pedido(
    solicitante,
    sector_origen,
    detalles,
    destinos,
    prioridad="normal",
    observaciones="",
    fecha=None,
):
    """
    Crea un pedido interno completo.

    - detalles: iterable de dicts con claves
      {producto, servicio, descripcion, cantidad, observacion}.
    - destinos: iterable de Sector (o ids) hacia los que se dirige.
    """
    pedido = PedidoInterno(
        solicitante=solicitante,
        sector_origen=sector_origen,
        prioridad=prioridad,
        observaciones=observaciones or "",
    )
    if fecha:
        pedido.fecha = fecha
    pedido.save()

    for item in detalles:
        PedidoInternoDetalle.objects.create(
            pedido=pedido,
            producto=item.get("producto"),
            servicio=item.get("servicio"),
            descripcion=item.get("descripcion", "") or "",
            cantidad=item.get("cantidad", 1) or 1,
            observacion=item.get("observacion", "") or "",
        )

    for sector in destinos:
        sector_obj = sector if isinstance(sector, Sector) else Sector.objects.get(pk=sector)
        PedidoDestino.objects.get_or_create(
            pedido=pedido,
            sector_destino=sector_obj,
        )

    pedido.registrar_movimiento(
        usuario=solicitante,
        accion="creado",
        detalle=f"Pedido creado desde {sector_origen.codigo}.",
    )

    return pedido


@transaction.atomic
def marcar_leido(destino, usuario):
    """Marca como leído un PedidoDestino y registra el movimiento."""
    if not destino.leido:
        destino.leido = True
        destino.fecha_leido = timezone.now()
        if destino.responsable_id is None and usuario is not None:
            destino.responsable = usuario
        destino.save(update_fields=["leido", "fecha_leido", "responsable"])

        destino.pedido.registrar_movimiento(
            usuario=usuario,
            accion="leido",
            detalle=f"Leído por sector {destino.sector_destino.codigo}.",
        )

    return destino


@transaction.atomic
def cambiar_estado(pedido, nuevo_estado, usuario, detalle=""):
    """Cambia el estado de la cabecera y deja constancia en el historial."""
    estados_validos = {c[0] for c in PedidoInterno.ESTADO_CHOICES}
    if nuevo_estado not in estados_validos:
        raise ValidationError(f"Estado inválido: {nuevo_estado}")

    pedido.estado = nuevo_estado
    pedido.save(update_fields=["estado", "actualizado"])

    accion = nuevo_estado if nuevo_estado in {a[0] for a in _acciones()} else "comentario"
    pedido.registrar_movimiento(
        usuario=usuario,
        accion=accion,
        detalle=detalle or f"Estado cambiado a {nuevo_estado}.",
    )

    return pedido


@transaction.atomic
def derivar(pedido, sector_destino, usuario, motivo=""):
    """
    Deriva un pedido hacia un nuevo sector: crea su PedidoDestino,
    pone el pedido en 'derivado' y registra el movimiento.
    """
    sector_obj = (
        sector_destino
        if isinstance(sector_destino, Sector)
        else Sector.objects.get(pk=sector_destino)
    )

    PedidoDestino.objects.get_or_create(
        pedido=pedido,
        sector_destino=sector_obj,
    )

    pedido.estado = "derivado"
    pedido.save(update_fields=["estado", "actualizado"])

    pedido.registrar_movimiento(
        usuario=usuario,
        accion="derivado",
        detalle=motivo or f"Derivado a {sector_obj.codigo}.",
    )

    return pedido


def _acciones():
    from ..models import PedidoMovimiento
    return PedidoMovimiento.ACCION_CHOICES
