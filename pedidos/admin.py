# gestion_pedidos/pedidos/admin.py

from django.contrib import admin

from .models import Pedido, PedidoItem


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    readonly_fields = ("subtotal",)
    fields = (
        "tipo_item",
        "producto",
        "servicio",
        "nombre_snapshot",
        "codigo_snapshot",
        "precio_unitario_snapshot",
        "cantidad",
        "subtotal",
    )


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cliente_web",
        "cliente",
        "estado",
        "subtotal",
        "total",
        "activo",
        "creado",
    )
    list_filter = ("estado", "activo", "creado")
    search_fields = (
        "id",
        "cliente__nombre",
        "cliente__apellido",
        "cliente__documento",
        "cliente__email",
    )
    ordering = ("-id",)
    readonly_fields = ("subtotal", "total", "creado", "actualizado")
    fields = (
        "cliente_web",
        "cliente",
        "estado",
        "observaciones_cliente",
        "observaciones_internas",
        "subtotal",
        "total",
        "activo",
        "creado",
        "actualizado",
    )
    inlines = [PedidoItemInline]


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pedido",
        "tipo_item",
        "nombre_snapshot",
        "cantidad",
        "precio_unitario_snapshot",
        "subtotal",
    )
    list_filter = ("tipo_item",)
    search_fields = ("nombre_snapshot", "codigo_snapshot")
    ordering = ("-id",)
    readonly_fields = ("subtotal",)
    fields = (
        "pedido",
        "tipo_item",
        "producto",
        "servicio",
        "nombre_snapshot",
        "codigo_snapshot",
        "precio_unitario_snapshot",
        "cantidad",
        "subtotal",
    )