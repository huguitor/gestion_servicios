from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from cobranzas.models import Cobro, FacturaCobranza


@transaction.atomic
def registrar_cobro(*, factura, registrado_por, **datos):
    """Registra un cobro bloqueando la factura para evitar sobrepagos concurrentes."""
    factura_bloqueada = FacturaCobranza.objects.select_for_update().get(pk=factura.pk)
    importe = datos.get("importe")
    if importe is None or importe <= Decimal("0.00"):
        raise ValidationError({"importe": "El importe debe ser mayor que cero."})

    if factura_bloqueada.es_nota_credito:
        raise ValidationError(
            {"factura": "Una Nota de Crédito no puede registrarse como cobro."}
        )
    saldo = factura_bloqueada.saldo_pendiente
    if importe > saldo:
        raise ValidationError(
            {"importe": f"El cobro supera el saldo pendiente ({saldo})."}
        )

    cobro = Cobro(
        factura=factura_bloqueada,
        registrado_por=registrado_por,
        **datos,
    )
    cobro.full_clean()
    cobro.save()
    return cobro
