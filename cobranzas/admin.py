from django.contrib import admin

from .models import Cobro, FacturaCobranza, SeguimientoCobranza


class CobroInline(admin.TabularInline):
    model = Cobro
    extra = 0
    can_delete = False
    readonly_fields = ("registrado_por", "creado", "actualizado")


class SeguimientoInline(admin.TabularInline):
    model = SeguimientoCobranza
    extra = 0
    can_delete = False
    readonly_fields = ("registrado_por", "creado")


@admin.register(FacturaCobranza)
class FacturaCobranzaAdmin(admin.ModelAdmin):
    list_display = (
        "numero_completo",
        "cliente",
        "fecha_factura",
        "total",
        "fecha_estimada_cobro",
    )
    search_fields = (
        "cliente__nombre",
        "cliente__apellido",
        "orden_compra",
        "presupuesto_referencia",
    )
    list_filter = ("tipo_comprobante", "fecha_factura", "fecha_estimada_manual")
    filter_horizontal = ("remitos",)
    inlines = (CobroInline, SeguimientoInline)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = ("factura", "fecha_cobro", "importe", "medio_pago", "registrado_por")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeguimientoCobranza)
class SeguimientoCobranzaAdmin(admin.ModelAdmin):
    list_display = ("factura", "fecha", "tipo", "registrado_por")

    def has_delete_permission(self, request, obj=None):
        return False
