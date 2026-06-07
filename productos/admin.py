from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from archivos.models import ArchivoRelacion

from .models import (
    MovimientoStock,
    Producto,
    ProductoImpuesto,
    Servicio,
    ServicioImpuesto,
)

# -------------------------
# IMPUESTOS PRODUCTO
# -------------------------
class ProductoImpuestoInline(admin.TabularInline):
    model = ProductoImpuesto
    extra = 1
    autocomplete_fields = ("impuesto",)


# -------------------------
# MOVIMIENTO STOCK (SOLO LECTURA)
# -------------------------
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


# -------------------------
# MULTIMEDIA DEBUG (NUEVO)
# -------------------------
class ArchivoRelacionInline(admin.TabularInline):
    model = ArchivoRelacion
    extra = 0
    fields = ("archivo", "rol", "orden", "observaciones")

    readonly_fields = ()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(
            content_type=ContentType.objects.get_for_model(Producto)
        )


# -------------------------
# PRODUCTO ADMIN
# -------------------------
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
        "archivos_debug",
    )

    # inlines = [
    #    ProductoImpuestoInline,
    #    MovimientoStockInline,
    #    ArchivoRelacionInline,  # 👈 NUEVO
    #]

    # -------------------------
    # DEBUG MULTIMEDIA
    # -------------------------
    def archivos_debug(self, obj):
        relaciones = obj.archivo_relaciones.select_related("archivo").all()

        if not relaciones:
            return "Sin archivos"

        return "\n".join(
            f"[{r.rol}] {r.archivo.nombre} → {r.archivo.archivo.url}"
            for r in relaciones
        )

    archivos_debug.short_description = "Multimedia (DEBUG)"


# -------------------------
# SERVICIOS
# -------------------------
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


# -------------------------
# MOVIMIENTO STOCK ADMIN
# -------------------------
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

    ordering = ("-creado", "-id")

    date_hierarchy = "creado"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False