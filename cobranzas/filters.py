from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from .models import FacturaCobranza


class FacturaCobranzaFilter(filters.FilterSet):
    estado = filters.ChoiceFilter(
        choices=[
            ("pendiente", "Pendiente"),
            ("parcial", "Parcial"),
            ("pagado", "Pagado"),
        ],
        method="filter_estado",
    )
    semaforo = filters.ChoiceFilter(
        choices=[
            ("gris", "Gris"),
            ("verde", "Verde"),
            ("amarillo", "Amarillo"),
            ("rojo", "Rojo"),
        ],
        method="filter_semaforo",
    )
    vencidas = filters.BooleanFilter(method="filter_vencidas")
    numero_factura = filters.CharFilter(method="filter_numero_factura")
    orden_compra = filters.CharFilter(lookup_expr="icontains")
    remito = filters.NumberFilter(field_name="remitos__id")
    presupuesto = filters.NumberFilter(field_name="presupuesto_id")
    fecha_factura_desde = filters.DateFilter(field_name="fecha_factura", lookup_expr="gte")
    fecha_factura_hasta = filters.DateFilter(field_name="fecha_factura", lookup_expr="lte")
    fecha_estimada_desde = filters.DateFilter(
        field_name="fecha_estimada_cobro", lookup_expr="gte"
    )
    fecha_estimada_hasta = filters.DateFilter(
        field_name="fecha_estimada_cobro", lookup_expr="lte"
    )
    con_saldo_pendiente = filters.BooleanFilter(method="filter_con_saldo")
    pagadas = filters.BooleanFilter(method="filter_pagadas")
    proximas_a_vencer = filters.BooleanFilter(method="filter_proximas")

    class Meta:
        model = FacturaCobranza
        fields = ["cliente", "tipo_comprobante"]

    def filter_estado(self, queryset, name, value):
        if value == "pendiente":
            return queryset.filter(_total_cobrado=Decimal("0.00"))
        if value == "parcial":
            return queryset.filter(
                _total_cobrado__gt=Decimal("0.00"),
                _total_cobrado__lt=models_f("total"),
            )
        if value == "pagado":
            return queryset.filter(_total_cobrado=models_f("total"))
        return queryset

    def filter_semaforo(self, queryset, name, value):
        hoy = timezone.localdate()
        limite = hoy + timedelta(days=7)
        con_saldo = Q(_total_cobrado__lt=models_f("total"))
        if value == "gris":
            return queryset.filter(_total_cobrado=models_f("total"))
        if value == "rojo":
            return queryset.filter(con_saldo, fecha_estimada_cobro__lt=hoy)
        if value == "amarillo":
            return queryset.filter(
                con_saldo,
                fecha_estimada_cobro__gte=hoy,
                fecha_estimada_cobro__lte=limite,
            )
        if value == "verde":
            return queryset.filter(con_saldo).filter(
                Q(fecha_estimada_cobro__gt=limite)
                | Q(fecha_estimada_cobro__isnull=True)
            )
        return queryset

    def filter_vencidas(self, queryset, name, value):
        condicion = Q(
            _total_cobrado__lt=models_f("total"),
            fecha_estimada_cobro__lt=timezone.localdate(),
        )
        return queryset.filter(condicion) if value else queryset.exclude(condicion)

    def filter_numero_factura(self, queryset, name, value):
        limpio = value.strip()
        if "-" in limpio:
            punto, numero = limpio.split("-", 1)
            if punto.isdigit() and numero.isdigit():
                return queryset.filter(
                    punto_venta=int(punto),
                    numero_factura=int(numero),
                )
        if limpio.isdigit():
            return queryset.filter(numero_factura=int(limpio))
        return queryset.none()

    def filter_con_saldo(self, queryset, name, value):
        condicion = Q(_total_cobrado__lt=models_f("total"))
        return queryset.filter(condicion) if value else queryset.exclude(condicion)

    def filter_pagadas(self, queryset, name, value):
        condicion = Q(_total_cobrado=models_f("total"))
        return queryset.filter(condicion) if value else queryset.exclude(condicion)

    def filter_proximas(self, queryset, name, value):
        hoy = timezone.localdate()
        condicion = Q(
            _total_cobrado__lt=models_f("total"),
            fecha_estimada_cobro__gte=hoy,
            fecha_estimada_cobro__lte=hoy + timedelta(days=7),
        )
        return queryset.filter(condicion) if value else queryset.exclude(condicion)


def models_f(field):
    # Helper local para mantener legibles las comparaciones contra campos anotados.
    from django.db.models import F

    return F(field)
