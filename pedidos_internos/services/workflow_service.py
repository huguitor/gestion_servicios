# backend/pedidos_internos/services/workflow_service.py

"""
Motor de workflow para pedidos internos.

Este servicio concentra todas las acciones operativas sobre PedidoDestino:

- marcar lectura;
- tomar el pedido;
- iniciar proceso;
- resolver;
- rechazar;
- derivar;
- cancelar el pedido completo;
- registrar movimientos;
- recalcular el estado global.

El pedido pertenece operativamente al sector.
El responsable es solamente el referente principal.
Los demás miembros activos del sector pueden continuar el proceso.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models.movimiento import PedidoMovimiento
from ..models.pedido import PedidoInterno
from ..models.pedido_destino import PedidoDestino
from ..models.sector import Sector
from .sla_service import (
    HITO_ENVIADO,
    HITO_LEIDO,
    HITO_RECIBIDO,
    HITO_EN_PROCESO,
    HITO_RESUELTO,
    evaluar_y_guardar,
)
from . import workflow_permissions


# ==========================================================
# TRANSICIONES PERMITIDAS DE PEDIDO DESTINO
# ==========================================================

TRANSICIONES_DESTINO = {
    PedidoDestino.Estado.PENDIENTE: {
        PedidoDestino.Estado.RECIBIDO,
        PedidoDestino.Estado.RECHAZADO,
    },
    PedidoDestino.Estado.RECIBIDO: {
        PedidoDestino.Estado.EN_PROCESO,
        PedidoDestino.Estado.RECHAZADO,
    },
    PedidoDestino.Estado.EN_PROCESO: {
        PedidoDestino.Estado.RESUELTO,
        PedidoDestino.Estado.RECHAZADO,
    },
    PedidoDestino.Estado.RESUELTO: set(),
    PedidoDestino.Estado.RECHAZADO: set(),
}


# ==========================================================
# MARCAR LEÍDO
# ==========================================================

@transaction.atomic
def marcar_leido(*, destino, usuario):
    """
    Registra la primera apertura del detalle por un integrante
    activo del sector destino.

    La lectura:

    - no asigna responsable;
    - no cambia el estado;
    - es idempotente;
    - registra solamente la primera lectura.
    """

    destino = _bloquear_destino(destino)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino.sector_destino,
    )

    _validar_pedido_no_cancelado(destino.pedido)

    if destino.leido:
        return destino

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino,
        permitido=workflow_permissions.puede_marcar_leido(
            usuario,
            destino,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para marcar este destino como leído.",
    )

    ahora = timezone.now()

    destino.leido = True
    destino.fecha_leido = ahora
    destino.leido_por = usuario

    destino.save(
        update_fields=[
            "leido",
            "fecha_leido",
            "leido_por",
            "actualizado",
        ]
    )

    movimiento = _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.LEIDO,
        estado_anterior=destino.estado,
        estado_nuevo=destino.estado,
        detalle=(
            f"Pedido abierto por primera vez en el sector "
            f"{destino.sector_destino.codigo}."
        ),
        metadata={
            "sector_destino_id": destino.sector_destino_id,
            "leido_por_id": usuario.pk,
        },
    )

    fecha_envio = _obtener_fecha_movimiento(
        destino=destino,
        accion=PedidoMovimiento.Accion.ENVIADO,
    )

    evaluar_y_guardar(
        movimiento=movimiento,
        destino=destino,
        hito_origen=HITO_ENVIADO,
        hito_destino=HITO_LEIDO,
        fecha_inicio=fecha_envio or destino.creado,
        fecha_fin=ahora,
    )

    return destino


# ==========================================================
# TOMAR PEDIDO / RECIBIR
# ==========================================================

@transaction.atomic
def tomar_pedido(*, destino, usuario, detalle=""):
    """
    El sector acepta formalmente gestionar el pedido.

    El usuario que ejecuta la acción queda como responsable principal.

    El responsable no bloquea al resto del sector.
    """

    destino = _bloquear_destino(destino)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino.sector_destino,
    )

    _validar_pedido_no_cancelado(destino.pedido)

    if destino.estado == PedidoDestino.Estado.RECIBIDO:
        if destino.responsable_id == usuario.pk:
            return destino

        raise ValidationError({
            "estado": (
                "El pedido ya fue recibido por otro responsable."
            )
        })

    if not destino.leido or destino.fecha_leido is None:
        raise ValidationError({
            "leido": (
                "El pedido debe abrirse y marcarse como leído "
                "antes de ser recibido."
            )
        })

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino,
        permitido=workflow_permissions.puede_tomar(
            usuario,
            destino,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para recibir este destino.",
    )

    _validar_transicion(
        estado_actual=destino.estado,
        nuevo_estado=PedidoDestino.Estado.RECIBIDO,
    )

    estado_anterior = destino.estado
    fecha_inicio_sla = destino.fecha_leido
    ahora = timezone.now()

    destino.estado = PedidoDestino.Estado.RECIBIDO
    destino.responsable = usuario
    destino.fecha_estado = ahora

    destino.save(
        update_fields=[
            "estado",
            "responsable",
            "fecha_estado",
            "actualizado",
        ]
    )

    movimiento = _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.RECIBIDO,
        estado_anterior=estado_anterior,
        estado_nuevo=destino.estado,
        detalle=(
            detalle
            or (
                f"Pedido recibido por "
                f"{_nombre_usuario(usuario)} en el sector "
                f"{destino.sector_destino.codigo}."
            )
        ),
        metadata={
            "sector_destino_id": destino.sector_destino_id,
            "responsable_id": usuario.pk,
        },
    )

    evaluar_y_guardar(
        movimiento=movimiento,
        destino=destino,
        hito_origen=HITO_LEIDO,
        hito_destino=HITO_RECIBIDO,
        fecha_inicio=fecha_inicio_sla,
        fecha_fin=ahora,
    )

    _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.RESPONSABLE_ASIGNADO,
        estado_anterior=destino.estado,
        estado_nuevo=destino.estado,
        detalle=(
            f"{_nombre_usuario(usuario)} quedó como responsable "
            f"principal del sector {destino.sector_destino.codigo}."
        ),
        metadata={
            "responsable_id": usuario.pk,
        },
    )

    _recalcular_estado_global(destino.pedido)

    return destino


# ==========================================================
# INICIAR PROCESO
# ==========================================================

@transaction.atomic
def iniciar_proceso(*, destino, usuario, detalle=""):
    """
    Indica que el sector comenzó el trabajo efectivo.

    Puede ejecutarlo cualquier miembro activo del sector.
    El responsable principal no se modifica.
    """

    destino = _bloquear_destino(destino)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino.sector_destino,
    )

    _validar_pedido_no_cancelado(destino.pedido)

    if destino.estado == PedidoDestino.Estado.EN_PROCESO:
        return destino

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino,
        permitido=workflow_permissions.puede_iniciar_proceso(
            usuario,
            destino,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para iniciar este destino.",
    )

    _validar_transicion(
        estado_actual=destino.estado,
        nuevo_estado=PedidoDestino.Estado.EN_PROCESO,
    )

    if destino.responsable_id is None:
        raise ValidationError({
            "responsable": (
                "El pedido debe ser recibido y tener un responsable "
                "antes de iniciar el proceso."
            )
        })

    estado_anterior = destino.estado
    fecha_inicio_sla = destino.fecha_estado
    ahora = timezone.now()

    destino.estado = PedidoDestino.Estado.EN_PROCESO
    destino.fecha_estado = ahora

    destino.save(
        update_fields=[
            "estado",
            "fecha_estado",
            "actualizado",
        ]
    )

    movimiento = _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.EN_PROCESO,
        estado_anterior=estado_anterior,
        estado_nuevo=destino.estado,
        detalle=(
            detalle
            or (
                f"El sector {destino.sector_destino.codigo} "
                f"inició el procesamiento."
            )
        ),
        metadata={
            "sector_destino_id": destino.sector_destino_id,
            "usuario_interviniente_id": usuario.pk,
        },
    )

    evaluar_y_guardar(
        movimiento=movimiento,
        destino=destino,
        hito_origen=HITO_RECIBIDO,
        hito_destino=HITO_EN_PROCESO,
        fecha_inicio=fecha_inicio_sla,
        fecha_fin=ahora,
    )

    _recalcular_estado_global(destino.pedido)

    return destino


# ==========================================================
# RESOLVER
# ==========================================================

@transaction.atomic
def resolver(*, destino, usuario, resultado):
    """
    Finaliza correctamente el trabajo de un sector.

    El resultado es obligatorio.
    Puede resolver cualquier miembro activo del sector.
    """

    resultado = (resultado or "").strip()

    if not resultado:
        raise ValidationError({
            "resultado": (
                "Debe indicar el resultado de la gestión."
            )
        })

    destino = _bloquear_destino(destino)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino.sector_destino,
    )

    _validar_pedido_no_cancelado(destino.pedido)

    if destino.estado == PedidoDestino.Estado.RESUELTO:
        return destino

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino,
        permitido=workflow_permissions.puede_resolver(
            usuario,
            destino,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para resolver este destino.",
    )

    _validar_transicion(
        estado_actual=destino.estado,
        nuevo_estado=PedidoDestino.Estado.RESUELTO,
    )

    estado_anterior = destino.estado
    fecha_inicio_sla = destino.fecha_estado
    ahora = timezone.now()

    destino.estado = PedidoDestino.Estado.RESUELTO
    destino.fecha_estado = ahora
    destino.observacion = resultado

    destino.save(
        update_fields=[
            "estado",
            "fecha_estado",
            "observacion",
            "actualizado",
        ]
    )

    movimiento = _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.RESUELTO,
        estado_anterior=estado_anterior,
        estado_nuevo=destino.estado,
        detalle=resultado,
        metadata={
            "sector_destino_id": destino.sector_destino_id,
            "resuelto_por_id": usuario.pk,
        },
    )

    evaluar_y_guardar(
        movimiento=movimiento,
        destino=destino,
        hito_origen=HITO_EN_PROCESO,
        hito_destino=HITO_RESUELTO,
        fecha_inicio=fecha_inicio_sla,
        fecha_fin=ahora,
    )

    _recalcular_estado_global(destino.pedido)

    return destino


# ==========================================================
# RECHAZAR
# ==========================================================

@transaction.atomic
def rechazar(*, destino, usuario, motivo):
    """
    Finaliza el destino como rechazado.

    El motivo es obligatorio.
    """

    motivo = (motivo or "").strip()

    if not motivo:
        raise ValidationError({
            "motivo": "Debe indicar el motivo del rechazo."
        })

    destino = _bloquear_destino(destino)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino.sector_destino,
    )

    _validar_pedido_no_cancelado(destino.pedido)

    if destino.estado == PedidoDestino.Estado.RECHAZADO:
        return destino

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino,
        permitido=workflow_permissions.puede_rechazar(
            usuario,
            destino,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para rechazar este destino.",
    )

    _validar_transicion(
        estado_actual=destino.estado,
        nuevo_estado=PedidoDestino.Estado.RECHAZADO,
    )

    estado_anterior = destino.estado

    destino.estado = PedidoDestino.Estado.RECHAZADO
    destino.fecha_estado = timezone.now()
    destino.observacion = motivo

    destino.save(
        update_fields=[
            "estado",
            "fecha_estado",
            "observacion",
            "actualizado",
        ]
    )

    _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.RECHAZADO,
        estado_anterior=estado_anterior,
        estado_nuevo=destino.estado,
        detalle=motivo,
        metadata={
            "sector_destino_id": destino.sector_destino_id,
            "rechazado_por_id": usuario.pk,
        },
    )

    _recalcular_estado_global(destino.pedido)

    return destino


# ==========================================================
# AGREGAR COMENTARIO
# ==========================================================

@transaction.atomic
def agregar_comentario(*, destino, usuario, comentario):
    """
    Registra una intervención sin modificar estado ni responsable.
    """

    comentario = (comentario or "").strip()

    if not comentario:
        raise ValidationError({
            "comentario": "El comentario no puede estar vacío."
        })

    destino = _bloquear_destino(destino)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino.sector_destino,
    )

    _validar_pedido_no_cancelado(destino.pedido)

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino,
        permitido=workflow_permissions.puede_comentar(
            usuario,
            destino,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para comentar este destino.",
    )

    _registrar_movimiento(
        pedido=destino.pedido,
        destino=destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.COMENTARIO,
        estado_anterior=destino.estado,
        estado_nuevo=destino.estado,
        detalle=comentario,
        metadata={
            "sector_destino_id": destino.sector_destino_id,
        },
    )

    return destino


# ==========================================================
# DERIVAR
# ==========================================================

@transaction.atomic
def derivar(
    *,
    destino_origen,
    sector_destino,
    usuario,
    motivo="",
):
    """
    Agrega un nuevo sector destino al pedido.

    Derivar no reemplaza ni desactiva el destino original.
    El destino original conserva su estado y responsable.
    """

    destino_origen = _bloquear_destino(destino_origen)

    _validar_usuario_activo(usuario)
    _validar_miembro_sector(
        usuario=usuario,
        sector=destino_origen.sector_destino,
    )

    _validar_pedido_no_cancelado(destino_origen.pedido)

    _validar_permiso_accion(
        usuario=usuario,
        destino=destino_origen,
        permitido=workflow_permissions.puede_derivar(
            usuario,
            destino_origen,
            _miembro_activo=True,
        ),
        mensaje="No tiene permiso para derivar este destino.",
    )

    if destino_origen.es_terminal:
        raise ValidationError({
            "estado": (
                "No se puede derivar desde un destino terminado."
            )
        })

    nuevo_sector = _obtener_sector_activo(sector_destino)

    if nuevo_sector.pk == destino_origen.sector_destino_id:
        raise ValidationError({
            "sector_destino": (
                "No se puede derivar al mismo sector."
            )
        })

    if nuevo_sector.pk == destino_origen.pedido.sector_origen_id:
        raise ValidationError({
            "sector_destino": (
                "No se puede derivar al sector de origen "
                "como nuevo destino."
            )
        })

    existente = PedidoDestino.objects.filter(
        pedido=destino_origen.pedido,
        sector_destino=nuevo_sector,
    ).first()

    if existente:
        raise ValidationError({
            "sector_destino": (
                "Ese sector ya forma parte del pedido."
            )
        })

    try:
        with transaction.atomic():
            nuevo_destino = PedidoDestino.objects.create(
                pedido=destino_origen.pedido,
                sector_destino=nuevo_sector,
                estado=PedidoDestino.Estado.PENDIENTE,
            )
    except IntegrityError as exc:
        raise ValidationError({
            "sector_destino": (
                "Ese sector ya forma parte del pedido."
            )
        }) from exc

    texto_movimiento = (
        (motivo or "").strip()
        or (
            f"Pedido derivado desde "
            f"{destino_origen.sector_destino.codigo} hacia "
            f"{nuevo_sector.codigo}."
        )
    )

    _registrar_movimiento(
        pedido=destino_origen.pedido,
        destino=destino_origen,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.DERIVADO,
        estado_anterior=destino_origen.estado,
        estado_nuevo=destino_origen.estado,
        detalle=texto_movimiento,
        metadata={
            "sector_origen_derivacion_id": (
                destino_origen.sector_destino_id
            ),
            "sector_destino_derivacion_id": nuevo_sector.pk,
            "nuevo_destino_id": nuevo_destino.pk,
        },
    )

    _registrar_movimiento(
        pedido=destino_origen.pedido,
        destino=nuevo_destino,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.ENVIADO,
        estado_anterior=None,
        estado_nuevo=PedidoDestino.Estado.PENDIENTE,
        detalle=(
            f"Pedido enviado al sector {nuevo_sector.codigo} "
            f"por derivación."
        ),
        metadata={
            "derivado_desde_destino_id": destino_origen.pk,
            "sector_destino_id": nuevo_sector.pk,
        },
    )

    _recalcular_estado_global(destino_origen.pedido)

    return nuevo_destino


# ==========================================================
# CANCELAR PEDIDO COMPLETO
# ==========================================================

@transaction.atomic
def cancelar_pedido(*, pedido, usuario, motivo):
    """
    Cancela lógicamente el pedido completo.

    Solo puede cancelar:

    - el solicitante;
    - un usuario staff;
    - un superusuario.
    """

    motivo = (motivo or "").strip()

    if not motivo:
        raise ValidationError({
            "motivo": (
                "Debe indicar el motivo de la cancelación."
            )
        })

    _validar_usuario_activo(usuario)

    pedido_id = pedido.pk if isinstance(pedido, PedidoInterno) else pedido

    try:
        pedido = (
            PedidoInterno.objects
            .select_for_update()
            .get(pk=pedido_id)
        )
    except PedidoInterno.DoesNotExist as exc:
        raise ValidationError(
            "El pedido indicado no existe."
        ) from exc

    autorizado = workflow_permissions.puede_cancelar(
        usuario,
        pedido,
        _validar_estado=False,
    )

    if not autorizado:
        raise ValidationError({
            "usuario": (
                "Solo el solicitante o un administrador "
                "pueden cancelar el pedido."
            )
        })

    if pedido.estado == PedidoInterno.Estado.CANCELADO:
        return pedido

    if pedido.estado in {
        PedidoInterno.Estado.RESUELTO,
        PedidoInterno.Estado.PARCIAL,
        PedidoInterno.Estado.RECHAZADO,
    }:
        raise ValidationError({
            "estado": (
                "No se puede cancelar un pedido finalizado."
            )
        })

    estado_anterior = pedido.estado

    pedido.estado = PedidoInterno.Estado.CANCELADO
    pedido.save(
        update_fields=[
            "estado",
            "actualizado",
        ]
    )

    _registrar_movimiento(
        pedido=pedido,
        destino=None,
        usuario=usuario,
        accion=PedidoMovimiento.Accion.CANCELADO,
        estado_anterior=estado_anterior,
        estado_nuevo=PedidoInterno.Estado.CANCELADO,
        detalle=motivo,
        metadata={
            "cancelado_por_id": usuario.pk,
        },
    )

    return pedido


# ==========================================================
# RECALCULAR ESTADO GLOBAL
# ==========================================================

def _recalcular_estado_global(pedido):
    """
    Calcula el estado de la cabecera a partir de sus destinos.

    Reglas:

    - pedido cancelado: no se modifica;
    - todos pendientes: pendiente;
    - alguno activo: en proceso;
    - todos resueltos: resuelto;
    - todos rechazados: rechazado;
    - mezcla final de resueltos y rechazados: parcial.
    """

    pedido = (
        PedidoInterno.objects
        .select_for_update()
        .get(pk=pedido.pk)
    )

    if pedido.estado == PedidoInterno.Estado.CANCELADO:
        return pedido.estado

    estados = list(
        pedido.destinos.values_list(
            "estado",
            flat=True,
        )
    )

    if not estados:
        nuevo_estado = PedidoInterno.Estado.PENDIENTE

    elif all(
        estado == PedidoDestino.Estado.PENDIENTE
        for estado in estados
    ):
        nuevo_estado = PedidoInterno.Estado.PENDIENTE

    elif all(
        estado == PedidoDestino.Estado.RESUELTO
        for estado in estados
    ):
        nuevo_estado = PedidoInterno.Estado.RESUELTO

    elif all(
        estado == PedidoDestino.Estado.RECHAZADO
        for estado in estados
    ):
        nuevo_estado = PedidoInterno.Estado.RECHAZADO

    elif all(
        estado in {
            PedidoDestino.Estado.RESUELTO,
            PedidoDestino.Estado.RECHAZADO,
        }
        for estado in estados
    ):
        nuevo_estado = PedidoInterno.Estado.PARCIAL

    else:
        nuevo_estado = PedidoInterno.Estado.EN_PROCESO

    if pedido.estado != nuevo_estado:
        pedido.estado = nuevo_estado
        pedido.save(
            update_fields=[
                "estado",
                "actualizado",
            ]
        )

    return nuevo_estado


# ==========================================================
# HELPERS DE VALIDACIÓN
# ==========================================================

def _bloquear_destino(destino):
    destino_id = (
        destino.pk
        if isinstance(destino, PedidoDestino)
        else destino
    )

    try:
        pedido_id = (
            PedidoDestino.objects
            .values_list("pedido_id", flat=True)
            .get(pk=destino_id)
        )

        pedido = (
            PedidoInterno.objects
            .select_for_update()
            .get(pk=pedido_id)
        )

        destino = (
            PedidoDestino.objects
            .select_for_update()
            .select_related(
                "sector_destino",
                "responsable",
            )
            .get(pk=destino_id)
        )
        destino.pedido = pedido
        return destino
    except (
        PedidoDestino.DoesNotExist,
        PedidoInterno.DoesNotExist,
    ) as exc:
        raise ValidationError(
            "El destino indicado no existe."
        ) from exc


def _validar_usuario_activo(usuario):
    if usuario is None:
        raise ValidationError(
            "Se requiere un usuario autenticado."
        )

    if not getattr(usuario, "is_authenticated", False):
        raise ValidationError(
            "Se requiere un usuario autenticado."
        )

    if not usuario.is_active:
        raise ValidationError(
            "El usuario se encuentra inactivo."
        )


def _validar_miembro_sector(*, usuario, sector):
    if not workflow_permissions.es_miembro_activo(usuario, sector):
        raise ValidationError({
            "usuario": (
                "El usuario no pertenece activamente "
                "al sector destino."
            )
        })


def _validar_permiso_accion(*, usuario, destino, permitido, mensaje):
    if not permitido:
        raise ValidationError({
            "usuario": mensaje,
        })


def _validar_pedido_no_cancelado(pedido):
    if pedido.estado == PedidoInterno.Estado.CANCELADO:
        raise ValidationError({
            "pedido": "El pedido se encuentra cancelado."
        })


def _validar_transicion(*, estado_actual, nuevo_estado):
    estados_destino_validos = {
        valor
        for valor, _etiqueta in PedidoDestino.Estado.choices
    }

    if nuevo_estado not in estados_destino_validos:
        raise ValidationError({
            "estado": f"Estado inválido: {nuevo_estado}."
        })

    permitidos = TRANSICIONES_DESTINO.get(estado_actual)

    if permitidos is None:
        raise ValidationError({
            "estado": (
                f"El estado actual '{estado_actual}' "
                "no está contemplado por el workflow."
            )
        })

    if nuevo_estado not in permitidos:
        raise ValidationError({
            "estado": (
                f"Transición inválida: "
                f"{estado_actual} → {nuevo_estado}."
            )
        })


def _obtener_sector_activo(sector):
    if isinstance(sector, Sector):
        if not sector.pk:
            raise ValidationError(
                "El sector todavía no fue guardado."
            )

        if not sector.activo:
            raise ValidationError({
                "sector_destino": (
                    "El sector destino se encuentra inactivo."
                )
            })

        return sector

    try:
        sector_id = int(sector)
    except (TypeError, ValueError):
        raise ValidationError({
            "sector_destino": (
                "El sector destino indicado no es válido."
            )
        })

    try:
        return Sector.objects.get(
            pk=sector_id,
            activo=True,
        )
    except Sector.DoesNotExist as exc:
        raise ValidationError({
            "sector_destino": (
                "El sector destino no existe "
                "o se encuentra inactivo."
            )
        }) from exc


def _registrar_movimiento(
    *,
    pedido,
    usuario,
    accion,
    detalle,
    destino=None,
    estado_anterior=None,
    estado_nuevo=None,
    metadata=None,
):
    return PedidoMovimiento.objects.create(
        pedido=pedido,
        destino=destino,
        usuario=usuario,
        accion=accion,
        detalle=detalle or "",
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        metadata=metadata or {},
    )


def _obtener_fecha_movimiento(*, destino, accion):
    movimiento = (
        PedidoMovimiento.objects
        .filter(
            destino=destino,
            accion=accion,
        )
        .order_by("fecha", "id")
        .first()
    )

    return movimiento.fecha if movimiento else None


def _nombre_usuario(usuario):
    nombre_completo = ""

    if hasattr(usuario, "get_full_name"):
        nombre_completo = usuario.get_full_name().strip()

    return nombre_completo or usuario.get_username()
