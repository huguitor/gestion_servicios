# backend/pedidos_internos/services/sla_service.py

"""
Servicio de control SLA para pedidos internos.

El SLA se configura por:

- sector;
- hito de origen;
- hito de destino;
- cantidad máxima de horas.

Ejemplos:

- enviado -> leido
- leido -> recibido
- recibido -> en_proceso
- en_proceso -> resuelto

Este servicio:

- determina el SLA activo de un PedidoDestino;
- calcula vencimiento y tiempo restante;
- evalúa transiciones terminadas;
- guarda el resultado histórico en PedidoMovimiento.

El frontend no calcula SLA: solamente muestra el resultado
devuelto por este servicio.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models.movimiento import PedidoMovimiento
from ..models.pedido_destino import PedidoDestino
from ..models.regla_sla import PedidoReglaSLA


# ==========================================================
# HITOS DEL WORKFLOW
# ==========================================================

HITO_ENVIADO = "enviado"
HITO_LEIDO = "leido"
HITO_RECIBIDO = "recibido"
HITO_EN_PROCESO = "en_proceso"
HITO_RESUELTO = "resuelto"
HITO_RECHAZADO = "rechazado"
HITO_CANCELADO = "cancelado"


# Cuando queda como máximo el 20 % del tiempo, se considera
# próximo a vencer.
PORCENTAJE_ALERTA = Decimal("0.20")


# ==========================================================
# ESTADOS VISUALES DEL SLA
# ==========================================================

SLA_SIN_REGLA = "sin_regla"
SLA_SIN_INICIO = "sin_inicio"
SLA_EN_TIEMPO = "en_tiempo"
SLA_PROXIMO_VENCER = "proximo_vencer"
SLA_VENCIDO = "vencido"
SLA_CUMPLIDO = "cumplido"
SLA_INCUMPLIDO = "incumplido"
SLA_FINALIZADO = "finalizado"


# ==========================================================
# SLA ACTUAL DE UN DESTINO
# ==========================================================

def obtener_sla_actual(*, destino, ahora=None):
    """
    Devuelve el estado del SLA actualmente activo para un destino.

    Resultado posible:

    {
        "aplica": True,
        "estado": "en_tiempo",
        "hito_origen": "leido",
        "hito_destino": "recibido",
        "fecha_inicio": datetime,
        "fecha_limite": datetime,
        "horas_limite": 8.0,
        "horas_transcurridas": 2.5,
        "horas_restantes": 5.5,
        "porcentaje_consumido": 31.25,
        "vencido": False,
    }

    Si no existe regla:

    {
        "aplica": False,
        "estado": "sin_regla",
        ...
    }
    """

    destino = _obtener_destino(destino)
    ahora = ahora or timezone.now()

    etapa = _determinar_etapa_actual(destino)

    if etapa is None:
        return {
            "aplica": False,
            "estado": SLA_FINALIZADO,
            "destino_id": destino.pk,
            "hito_origen": None,
            "hito_destino": None,
            "fecha_inicio": None,
            "fecha_limite": None,
            "horas_limite": None,
            "horas_transcurridas": None,
            "horas_restantes": None,
            "porcentaje_consumido": None,
            "vencido": False,
        }

    hito_origen = etapa["hito_origen"]
    hito_destino = etapa["hito_destino"]
    fecha_inicio = etapa["fecha_inicio"]

    regla = obtener_regla(
        sector=destino.sector_destino,
        hito_origen=hito_origen,
        hito_destino=hito_destino,
    )

    if regla is None:
        return {
            "aplica": False,
            "estado": SLA_SIN_REGLA,
            "destino_id": destino.pk,
            "hito_origen": hito_origen,
            "hito_destino": hito_destino,
            "fecha_inicio": fecha_inicio,
            "fecha_limite": None,
            "horas_limite": None,
            "horas_transcurridas": None,
            "horas_restantes": None,
            "porcentaje_consumido": None,
            "vencido": False,
        }

    if fecha_inicio is None:
        return {
            "aplica": True,
            "estado": SLA_SIN_INICIO,
            "destino_id": destino.pk,
            "regla_id": regla.pk,
            "hito_origen": hito_origen,
            "hito_destino": hito_destino,
            "fecha_inicio": None,
            "fecha_limite": None,
            "horas_limite": float(regla.horas_limite),
            "horas_transcurridas": None,
            "horas_restantes": None,
            "porcentaje_consumido": None,
            "vencido": False,
        }

    return _calcular_sla_en_curso(
        destino=destino,
        regla=regla,
        hito_origen=hito_origen,
        hito_destino=hito_destino,
        fecha_inicio=fecha_inicio,
        ahora=ahora,
    )


# ==========================================================
# EVALUAR UNA TRANSICIÓN FINALIZADA
# ==========================================================

def evaluar_transicion(
    *,
    destino,
    hito_origen,
    hito_destino,
    fecha_inicio,
    fecha_fin=None,
):
    """
    Evalúa una etapa ya finalizada.

    Se utiliza cuando ocurre una transición como:

    - enviado -> leído;
    - leído -> recibido;
    - recibido -> en proceso;
    - en proceso -> resuelto.

    No guarda datos. Solamente devuelve el resultado.
    """

    destino = _obtener_destino(destino)
    fecha_fin = fecha_fin or timezone.now()

    if fecha_inicio is None:
        return {
            "aplica": False,
            "estado": SLA_SIN_INICIO,
            "regla_id": None,
            "hito_origen": hito_origen,
            "hito_destino": hito_destino,
            "fecha_inicio": None,
            "fecha_fin": fecha_fin,
            "horas_limite": None,
            "duracion_horas": None,
            "vencido": None,
        }

    if fecha_fin < fecha_inicio:
        raise ValidationError(
            "La fecha final del SLA no puede ser anterior "
            "a la fecha inicial."
        )

    regla = obtener_regla(
        sector=destino.sector_destino,
        hito_origen=hito_origen,
        hito_destino=hito_destino,
    )

    if regla is None:
        return {
            "aplica": False,
            "estado": SLA_SIN_REGLA,
            "regla_id": None,
            "hito_origen": hito_origen,
            "hito_destino": hito_destino,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "horas_limite": None,
            "duracion_horas": _horas_entre(
                fecha_inicio,
                fecha_fin,
            ),
            "vencido": None,
        }

    duracion_horas = _horas_entre(
        fecha_inicio,
        fecha_fin,
    )

    horas_limite = _decimal(regla.horas_limite)
    vencido = duracion_horas > horas_limite

    return {
        "aplica": True,
        "estado": (
            SLA_INCUMPLIDO
            if vencido
            else SLA_CUMPLIDO
        ),
        "regla_id": regla.pk,
        "hito_origen": hito_origen,
        "hito_destino": hito_destino,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "horas_limite": horas_limite,
        "duracion_horas": duracion_horas,
        "vencido": vencido,
    }


# ==========================================================
# GUARDAR RESULTADO EN EL MOVIMIENTO
# ==========================================================

def guardar_resultado_en_movimiento(*, movimiento, resultado):
    """
    Guarda en PedidoMovimiento el resultado histórico del SLA.

    El movimiento debe corresponder al evento que cerró la etapa.

    Ejemplo:

    movimiento de acción "leido"
    guarda el resultado de "enviado -> leido".
    """

    if not isinstance(movimiento, PedidoMovimiento):
        try:
            movimiento = PedidoMovimiento.objects.get(
                pk=movimiento
            )
        except (
            PedidoMovimiento.DoesNotExist,
            TypeError,
            ValueError,
        ) as exc:
            raise ValidationError(
                "El movimiento indicado no existe."
            ) from exc

    aplica = bool(resultado.get("aplica"))

    movimiento.sla_aplica = aplica

    if aplica:
        movimiento.sla_limite_horas = resultado.get(
            "horas_limite"
        )
        movimiento.sla_duracion_horas = resultado.get(
            "duracion_horas"
        )
        movimiento.sla_vencido = resultado.get(
            "vencido"
        )
    else:
        movimiento.sla_limite_horas = None
        movimiento.sla_duracion_horas = resultado.get(
            "duracion_horas"
        )
        movimiento.sla_vencido = None

    metadata = dict(movimiento.metadata or {})

    metadata["sla"] = {
        "regla_id": resultado.get("regla_id"),
        "estado": resultado.get("estado"),
        "hito_origen": resultado.get("hito_origen"),
        "hito_destino": resultado.get("hito_destino"),
        "fecha_inicio": _isoformat(
            resultado.get("fecha_inicio")
        ),
        "fecha_fin": _isoformat(
            resultado.get("fecha_fin")
        ),
    }

    movimiento.metadata = metadata

    movimiento.save(
        update_fields=[
            "sla_aplica",
            "sla_limite_horas",
            "sla_duracion_horas",
            "sla_vencido",
            "metadata",
        ]
    )

    return movimiento


# ==========================================================
# EVALUAR Y GUARDAR
# ==========================================================

def evaluar_y_guardar(
    *,
    movimiento,
    destino,
    hito_origen,
    hito_destino,
    fecha_inicio,
    fecha_fin=None,
):
    """
    Atajo para evaluar una transición y guardar el resultado
    en el movimiento que cerró la etapa.
    """

    resultado = evaluar_transicion(
        destino=destino,
        hito_origen=hito_origen,
        hito_destino=hito_destino,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    guardar_resultado_en_movimiento(
        movimiento=movimiento,
        resultado=resultado,
    )

    return resultado


# ==========================================================
# BUSCAR REGLA
# ==========================================================

def obtener_regla(
    *,
    sector,
    hito_origen,
    hito_destino,
):
    """
    Busca la regla activa para un sector y una transición.

    Por diseño debe existir como máximo una regla activa para
    la misma combinación.
    """

    sector_id = (
        sector.pk
        if hasattr(sector, "pk")
        else sector
    )

    return (
        PedidoReglaSLA.objects
        .filter(
            sector_id=sector_id,
            hito_origen=hito_origen,
            hito_destino=hito_destino,
            activo=True,
        )
        .order_by("-actualizado", "-id")
        .first()
    )


# ==========================================================
# DETERMINAR ETAPA ACTUAL
# ==========================================================

def _determinar_etapa_actual(destino):
    """
    Determina qué SLA está corriendo en este momento.

    Reglas:

    - no leído:
        enviado -> leído

    - leído y pendiente:
        leído -> recibido

    - recibido:
        recibido -> en proceso

    - en proceso:
        en proceso -> resuelto

    - resuelto o rechazado:
        no tiene SLA activo
    """

    if destino.estado in {
        PedidoDestino.Estado.RESUELTO,
        PedidoDestino.Estado.RECHAZADO,
    }:
        return None

    if not destino.leido:
        return {
            "hito_origen": HITO_ENVIADO,
            "hito_destino": HITO_LEIDO,
            "fecha_inicio": _obtener_fecha_envio(destino),
        }

    if destino.estado == PedidoDestino.Estado.PENDIENTE:
        return {
            "hito_origen": HITO_LEIDO,
            "hito_destino": HITO_RECIBIDO,
            "fecha_inicio": destino.fecha_leido,
        }

    if destino.estado == PedidoDestino.Estado.RECIBIDO:
        return {
            "hito_origen": HITO_RECIBIDO,
            "hito_destino": HITO_EN_PROCESO,
            "fecha_inicio": destino.fecha_estado,
        }

    if destino.estado == PedidoDestino.Estado.EN_PROCESO:
        return {
            "hito_origen": HITO_EN_PROCESO,
            "hito_destino": HITO_RESUELTO,
            "fecha_inicio": destino.fecha_estado,
        }

    return None


# ==========================================================
# CÁLCULO EN CURSO
# ==========================================================

def _calcular_sla_en_curso(
    *,
    destino,
    regla,
    hito_origen,
    hito_destino,
    fecha_inicio,
    ahora,
):
    horas_limite = _decimal(regla.horas_limite)

    fecha_limite = fecha_inicio + timedelta(
        hours=float(horas_limite)
    )

    horas_transcurridas = _horas_entre(
        fecha_inicio,
        ahora,
    )

    horas_restantes = _decimal(
        horas_limite - horas_transcurridas
    )

    vencido = ahora > fecha_limite

    if vencido:
        estado = SLA_VENCIDO
    else:
        limite_alerta = horas_limite * PORCENTAJE_ALERTA

        if horas_restantes <= limite_alerta:
            estado = SLA_PROXIMO_VENCER
        else:
            estado = SLA_EN_TIEMPO

    if horas_limite > 0:
        porcentaje_consumido = _decimal(
            (horas_transcurridas / horas_limite)
            * Decimal("100")
        )
    else:
        porcentaje_consumido = Decimal("100")

    return {
        "aplica": True,
        "estado": estado,
        "destino_id": destino.pk,
        "regla_id": regla.pk,
        "hito_origen": hito_origen,
        "hito_destino": hito_destino,
        "fecha_inicio": fecha_inicio,
        "fecha_limite": fecha_limite,
        "horas_limite": horas_limite,
        "horas_transcurridas": horas_transcurridas,
        "horas_restantes": horas_restantes,
        "porcentaje_consumido": porcentaje_consumido,
        "vencido": vencido,
    }


# ==========================================================
# FECHA DEL ENVÍO AL DESTINO
# ==========================================================

def _obtener_fecha_envio(destino):
    """
    Obtiene el movimiento de envío asociado específicamente
    al destino.

    Ese movimiento es el inicio del SLA enviado -> leído.
    """

    movimiento = (
        PedidoMovimiento.objects
        .filter(
            destino=destino,
            accion=PedidoMovimiento.Accion.ENVIADO,
        )
        .order_by("fecha", "id")
        .first()
    )

    if movimiento:
        return movimiento.fecha

    # Compatibilidad temporal para destinos creados antes de que
    # existieran movimientos de envío por destino.
    return destino.creado


# ==========================================================
# HELPERS
# ==========================================================

def _obtener_destino(destino):
    if isinstance(destino, PedidoDestino):
        return destino

    try:
        return (
            PedidoDestino.objects
            .select_related(
                "pedido",
                "sector_destino",
            )
            .get(pk=destino)
        )
    except (
        PedidoDestino.DoesNotExist,
        TypeError,
        ValueError,
    ) as exc:
        raise ValidationError(
            "El destino indicado no existe."
        ) from exc


def _horas_entre(fecha_inicio, fecha_fin):
    segundos = Decimal(
        str(
            (
                fecha_fin - fecha_inicio
            ).total_seconds()
        )
    )

    return _decimal(
        segundos / Decimal("3600")
    )


def _decimal(valor):
    if valor is None:
        return None

    return Decimal(str(valor)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _isoformat(valor):
    if valor is None:
        return None

    return valor.isoformat()