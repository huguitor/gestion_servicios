from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from cobranzas.models import Cobro, FacturaCobranza


@transaction.atomic
def registrar_cobro(*, factura, registrado_por, **datos):
    """Registra un cobro bloqueando la factura para evitar sobrepagos concurrentes."""
    factura_bloqueada = FacturaCobranza.objects.select_for_update().get(pk=factura.pk)
    importe = datos.get("importe")
    if importe is None or importe <= Decimal("0.00"):
        raise ValidationError({"importe": "El importe debe ser mayor que cero."})

    total_cobrado = factura_bloqueada.cobros.aggregate(
        total=Sum("importe")
    )["total"] or Decimal("0.00")
    saldo = factura_bloqueada.total - total_cobrado
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
