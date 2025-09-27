# gestion/productos/admin.py
from django.contrib import admin
from .models import Producto, Servicio, ProductoImpuesto, ServicioImpuesto

# Inline para ProductoImpuesto
class ProductoImpuestoInline(admin.TabularInline):
    model = ProductoImpuesto
    extra = 1
    autocomplete_fields = ['impuesto']  # usa el ImpuestoAdmin que ya tiene search_fields

# Admin para Producto
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['sku', 'nombre', 'precio_venta', 'costo_compra', 'activo']
    inlines = [ProductoImpuestoInline]

# Inline para ServicioImpuesto
class ServicioImpuestoInline(admin.TabularInline):
    model = ServicioImpuesto
    extra = 1
    autocomplete_fields = ['impuesto']  # usa el ImpuestoAdmin que ya tiene search_fields

# Admin para Servicio
@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ['codigo_interno', 'nombre', 'precio_base', 'activo']
    inlines = [ServicioImpuestoInline]


