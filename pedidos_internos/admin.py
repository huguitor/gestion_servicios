# gestion/backend/pedidos_internos/admin.py

from django.contrib import admin

from .models import (
    Sector,
    UsuarioSector,
    PedidoInterno,
    PedidoInternoDetalle,
    PedidoDestino,
    PedidoMovimiento,
)


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "ciudad", "provincia", "activo")
    list_filter = ("activo", "provincia")
    search_fields = ("codigo", "nombre")
    ordering = ("codigo",)


@admin.register(UsuarioSector)
class UsuarioSectorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "sector", "principal", "activo")
    list_filter = ("activo", "principal", "sector")
    search_fields = ("usuario__username", "sector__codigo")
    autocomplete_fields = ("usuario",)


class PedidoInternoDetalleInline(admin.TabularInline):
    model = PedidoInternoDetalle
    extra = 0
    fields = ("producto", "servicio", "descripcion", "cantidad", "observacion")


class PedidoDestinoInline(admin.TabularInline):
    model = PedidoDestino
    extra = 0
    fields = ("sector_destino", "estado", "leido", "fecha_leido", "responsable", "observacion")
    readonly_fields = ("fecha_leido",)


class PedidoMovimientoInline(admin.TabularInline):
    model = PedidoMovimiento
    extra = 0
    fields = ("accion", "usuario", "detalle", "fecha")
    readonly_fields = ("fecha",)


@admin.register(PedidoInterno)
class PedidoInternoAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "fecha",
        "solicitante",
        "sector_origen",
        "estado",
        "prioridad",
        "creado",
    )
    list_filter = ("estado", "prioridad", "sector_origen")
    search_fields = ("numero", "solicitante__username", "observaciones")
    ordering = ("-id",)
    readonly_fields = ("numero", "creado", "actualizado")
    inlines = [
        PedidoInternoDetalleInline,
        PedidoDestinoInline,
        PedidoMovimientoInline,
    ]


@admin.register(PedidoDestino)
class PedidoDestinoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "sector_destino", "estado", "leido", "fecha_leido", "responsable")
    list_filter = ("estado", "leido", "sector_destino")
    search_fields = ("pedido__numero",)


@admin.register(PedidoMovimiento)
class PedidoMovimientoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "accion", "usuario", "fecha")
    list_filter = ("accion",)
    search_fields = ("pedido__numero", "detalle")
    readonly_fields = ("fecha",)
