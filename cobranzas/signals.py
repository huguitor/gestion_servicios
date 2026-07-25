from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import FacturaCobranza


@receiver(m2m_changed, sender=FacturaCobranza.remitos.through)
def validar_cliente_de_remitos(sender, instance, action, pk_set, reverse, **kwargs):
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return

    from remitos.models import Remito

    if reverse:
        facturas = (
            FacturaCobranza.objects.filter(pk__in=pk_set or set())
            if action != "pre_clear"
            else instance.facturas_cobranza.all()
        )
        for factura in facturas:
            if action == "pre_add":
                factura.validar_remitos([*factura.remitos.all(), instance])
            elif factura.cobros.exists():
                raise ValidationError(
                    {"remitos": "Los remitos no pueden modificarse después de registrar cobros."}
                )
        return

    if action == "pre_add":
        nuevos = list(Remito.objects.filter(pk__in=pk_set or set()))
        instance.validar_remitos([*instance.remitos.all(), *nuevos])
    elif instance.cobros.exists():
        raise ValidationError(
            {"remitos": "Los remitos no pueden modificarse después de registrar cobros."}
        )
