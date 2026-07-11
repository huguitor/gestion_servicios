"""Permisos de negocio para el workflow de pedidos internos.

Las funciones de este módulo no modifican estado ni lanzan excepciones.
Sirven tanto para informar acciones disponibles como para que el workflow
aplique exactamente las mismas reglas antes de operar.
"""

from ..models.pedido import PedidoInterno
from ..models.pedido_destino import PedidoDestino
from ..models.usuario_sector import UsuarioSector


def _usuario_activo(usuario):
    return bool(
        usuario is not None
        and getattr(usuario, "is_authenticated", False)
        and getattr(usuario, "is_active", False)
    )


def es_miembro_activo(usuario, sector):
    if not _usuario_activo(usuario) or sector is None:
        return False

    sector_id = getattr(sector, "pk", sector)

    return UsuarioSector.objects.filter(
        usuario_id=usuario.pk,
        sector_id=sector_id,
        activo=True,
        sector__activo=True,
    ).exists()


def _puede_operar(usuario, destino, *, _miembro_activo=None):
    if _miembro_activo is None and destino is not None:
        _miembro_activo = es_miembro_activo(
            usuario,
            destino.sector_destino_id,
        )

    return bool(
        destino is not None
        and destino.pedido.estado != PedidoInterno.Estado.CANCELADO
        and _miembro_activo
    )


def puede_marcar_leido(usuario, destino, *, _miembro_activo=None):
    return (
        _puede_operar(
            usuario,
            destino,
            _miembro_activo=_miembro_activo,
        )
        and not destino.leido
    )


def puede_tomar(usuario, destino, *, _miembro_activo=None):
    return bool(
        _puede_operar(
            usuario,
            destino,
            _miembro_activo=_miembro_activo,
        )
        and destino.estado == PedidoDestino.Estado.PENDIENTE
        and destino.leido
        and destino.fecha_leido is not None
    )


def puede_iniciar_proceso(usuario, destino, *, _miembro_activo=None):
    return bool(
        _puede_operar(
            usuario,
            destino,
            _miembro_activo=_miembro_activo,
        )
        and destino.estado == PedidoDestino.Estado.RECIBIDO
        and destino.responsable_id is not None
    )


def puede_comentar(usuario, destino, *, _miembro_activo=None):
    return _puede_operar(
        usuario,
        destino,
        _miembro_activo=_miembro_activo,
    )


def puede_derivar(usuario, destino, *, _miembro_activo=None):
    return (
        _puede_operar(
            usuario,
            destino,
            _miembro_activo=_miembro_activo,
        )
        and not destino.es_terminal
    )


def puede_resolver(usuario, destino, *, _miembro_activo=None):
    return bool(
        _puede_operar(
            usuario,
            destino,
            _miembro_activo=_miembro_activo,
        )
        and destino.estado == PedidoDestino.Estado.EN_PROCESO
    )


def puede_rechazar(usuario, destino, *, _miembro_activo=None):
    return bool(
        _puede_operar(
            usuario,
            destino,
            _miembro_activo=_miembro_activo,
        )
        and destino.estado in {
            PedidoDestino.Estado.PENDIENTE,
            PedidoDestino.Estado.RECIBIDO,
            PedidoDestino.Estado.EN_PROCESO,
        }
    )


def puede_cancelar(usuario, pedido, *, _validar_estado=True):
    if not _usuario_activo(usuario) or pedido is None:
        return False

    if _validar_estado and pedido.estado in {
        PedidoInterno.Estado.CANCELADO,
        PedidoInterno.Estado.RESUELTO,
        PedidoInterno.Estado.PARCIAL,
        PedidoInterno.Estado.RECHAZADO,
    }:
        return False

    return bool(
        pedido.solicitante_id == usuario.pk
        or usuario.is_staff
        or usuario.is_superuser
    )


def acciones_permitidas(usuario, destino):
    acciones = []
    miembro_activo = es_miembro_activo(
        usuario,
        destino.sector_destino_id,
    )

    if puede_marcar_leido(
        usuario,
        destino,
        _miembro_activo=miembro_activo,
    ):
        acciones.append("marcar_leido")

    if puede_tomar(usuario, destino, _miembro_activo=miembro_activo):
        acciones.append("tomar")

    if puede_iniciar_proceso(
        usuario,
        destino,
        _miembro_activo=miembro_activo,
    ):
        acciones.append("iniciar_proceso")

    if puede_comentar(usuario, destino, _miembro_activo=miembro_activo):
        acciones.append("comentar")

    if puede_derivar(usuario, destino, _miembro_activo=miembro_activo):
        acciones.append("derivar")

    if puede_resolver(usuario, destino, _miembro_activo=miembro_activo):
        acciones.append("resolver")

    if puede_rechazar(usuario, destino, _miembro_activo=miembro_activo):
        acciones.append("rechazar")

    return acciones
