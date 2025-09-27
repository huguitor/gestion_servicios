# gestion/presupuestos/admin.py
from django.contrib import admin
from decimal import Decimal
from .models import Presupuesto, PresupuestoItem


class PresupuestoItemInline(admin.TabularInline):
    model = PresupuestoItem
    extra = 0
    fields = ('producto', 'servicio', 'cantidad', 'precio_unitario', 'codigo', 'descripcion')
    readonly_fields = ('codigo', 'descripcion', 'precio_unitario')
    show_change_link = True


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'cliente', 'numero', 'estado', 'subtotal', 'iva_valor', 'total')
    inlines = [PresupuestoItemInline]
    search_fields = ('cliente__nombre', 'numero')
    list_filter = ('estado',)
    readonly_fields = ('subtotal', 'iva_valor', 'total')

    def save_related(self, request, form, formsets, change):
        """
        Después de guardar los ítems recalculamos subtotal, IVA y total.
        Esto asegura que no dependamos de refrescos en el frontend del admin.
        """
        super().save_related(request, form, formsets, change)

        obj = form.instance
        subtotal = Decimal('0.00')

        for item in obj.items.all():
            subtotal += (item.cantidad or 0) * (item.precio_unitario or Decimal('0.00'))

        obj.subtotal = subtotal
        obj.iva_valor = subtotal * (Decimal(obj.iva_porcentaje) / 100)
        obj.total = obj.subtotal + obj.iva_valor
        obj.save()
