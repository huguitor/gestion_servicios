# gestion/presupuestos/admin.py - VERSIÓN DEFINITIVA
from django.contrib import admin
from decimal import Decimal
from .models import Presupuesto, PresupuestoItem, PresupuestoAdjunto

class PresupuestoItemInline(admin.TabularInline):
    model = PresupuestoItem
    extra = 0
    fields = ('producto', 'servicio', 'cantidad', 'precio_unitario', 'codigo', 'descripcion')
    readonly_fields = ('codigo', 'descripcion')
    show_change_link = True

class PresupuestoAdjuntoInline(admin.TabularInline):
    model = PresupuestoAdjunto
    extra = 0
    fields = ('archivo', 'tipo', 'descripcion')
    show_change_link = True

@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'cliente', 'numero', 'estado', 'subtotal', 'iva_valor', 'total')
    inlines = [PresupuestoItemInline, PresupuestoAdjuntoInline]
    search_fields = ('cliente__nombre', 'numero')
    list_filter = ('estado',)
    readonly_fields = ('subtotal', 'iva_valor', 'total')

    def save_formset(self, request, form, formset, change):
        """
        Manejar específicamente los adjuntos para asignar el usuario automáticamente
        """
        if formset.model == PresupuestoAdjunto:
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.pk:  # Solo para nuevos adjuntos
                    instance.subido_por = request.user
                instance.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)

    def save_related(self, request, form, formsets, change):
        """
        Recalcular subtotal, IVA y total después de guardar
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

@admin.register(PresupuestoAdjunto)
class PresupuestoAdjuntoAdmin(admin.ModelAdmin):
    list_display = ('nombre_original', 'presupuesto', 'tipo', 'tamaño_formateado', 'subido_por', 'fecha_subida')
    list_filter = ('tipo', 'fecha_subida', 'es_publico')
    search_fields = ('nombre_original', 'descripcion', 'presupuesto__numero')
    readonly_fields = ('tamaño', 'extension', 'nombre_original', 'checksum', 'version', 'subido_por', 'fecha_subida', 'fecha_modificacion')
    fieldsets = (
        ('Información Principal', {
            'fields': ('presupuesto', 'archivo', 'tipo', 'descripcion', 'es_publico')
        }),
        ('Metadatos Automáticos', {
            'fields': ('nombre_original', 'tamaño', 'extension', 'checksum', 'version'),
            'classes': ('collapse',)
        }),
        ('Información de Auditoría', {
            'fields': ('subido_por', 'fecha_subida', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
        ('Metadatos Adicionales', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    def tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()
    tamaño_formateado.short_description = 'Tamaño'

    def save_model(self, request, obj, form, change):
        """Asignar automáticamente el usuario que sube el archivo"""
        if not change:  # Solo en creación
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)