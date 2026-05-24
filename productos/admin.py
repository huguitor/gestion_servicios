# gestion/backend/productos/admin.py

from django.contrib import admin

from .models import (
    MovimientoStock,
    Producto,
    ProductoImpuesto,
    Servicio,
    ServicioImpuesto,
)


class ProductoImpuestoInline(admin.TabularInline):
    model = ProductoImpuesto
    extra = 1
    autocomplete_fields = ("impuesto",)


class MovimientoStockInline(admin.TabularInline):
    model = MovimientoStock
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ("-creado", "-id")

    fields = (
        "creado",
        "tipo",
        "cantidad",
        "stock_anterior",
        "stock_nuevo",
        "stock_reservado_anterior",
        "stock_reservado_nuevo",
        "pedido",
        "observacion",
    )

    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "nombre",
        "precio_venta",
        "costo_compra",
        "stock",
        "stock_reservado",
        "stock_disponible",
        "activo",
    )

    search_fields = (
        "sku",
        "nombre",
        "codigo_barras",
    )

    list_filter = (
        "activo",
        "publicado_web",
        "destacado_web",
        "mostrar_en_home",
    )

    readonly_fields = (
        "stock_disponible",
    )

    inlines = [
        ProductoImpuestoInline,
        MovimientoStockInline,
    ]


class ServicioImpuestoInline(admin.TabularInline):
    model = ServicioImpuesto
    extra = 1
    autocomplete_fields = ("impuesto",)


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_interno",
        "nombre",
        "precio_base",
        "activo",
    )

    search_fields = (
        "codigo_interno",
        "nombre",
    )

    list_filter = (
        "activo",
        "publicado_web",
        "destacado_web",
        "mostrar_en_home",
    )

    inlines = [
        ServicioImpuestoInline,
    ]


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = (
        "creado",
        "producto",
        "tipo",
        "cantidad",
        "stock_anterior",
        "stock_nuevo",
        "stock_reservado_anterior",
        "stock_reservado_nuevo",
        "pedido",
        "observacion",
    )

    list_filter = (
        "tipo",
        "creado",
        "producto",
    )

    search_fields = (
        "producto__sku",
        "producto__nombre",
        "pedido__id",
        "observacion",
    )

    readonly_fields = (
        "producto",
        "tipo",
        "cantidad",
        "stock_anterior",
        "stock_nuevo",
        "stock_reservado_anterior",
        "stock_reservado_nuevo",
        "pedido",
        "observacion",
        "creado",
    )

    ordering = (
        "-creado",
        "-id",
    )

    date_hierarchy = "creado"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False