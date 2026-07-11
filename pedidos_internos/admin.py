from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import (
    PedidoDestino,
    PedidoInterno,
    PedidoInternoDetalle,
    PedidoMovimiento,
    PedidoReglaSLA,
    Sector,
    UsuarioSector,
)


class SinEliminacionAdminMixin:
    def has_delete_permission(self, request, obj=None):
        return False


class SoloLecturaAdminMixin(SinEliminacionAdminMixin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Sector)
class SectorAdmin(SinEliminacionAdminMixin, admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "ciudad",
        "provincia",
        "activo",
    )
    list_filter = ("activo", "provincia")
    search_fields = ("codigo", "nombre")
    ordering = ("codigo",)


class UsuarioSectorAdminForm(forms.ModelForm):
    class Meta:
        model = UsuarioSector
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        usuario = cleaned_data.get("usuario")

        if (
            usuario
            and cleaned_data.get("principal")
            and cleaned_data.get("activo")
        ):
            existente = UsuarioSector.objects.filter(
                usuario=usuario,
                principal=True,
                activo=True,
            )

            if self.instance.pk:
                existente = existente.exclude(pk=self.instance.pk)

            if existente.exists():
                raise ValidationError(
                    "El usuario ya tiene otro sector principal activo."
                )

        return cleaned_data


@admin.register(UsuarioSector)
class UsuarioSectorAdmin(admin.ModelAdmin):
    form = UsuarioSectorAdminForm
    list_display = ("usuario", "sector", "principal", "activo")
    list_filter = ("activo", "principal", "sector")
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "sector__codigo",
        "sector__nombre",
    )
    autocomplete_fields = ("usuario", "sector")
    list_select_related = ("usuario", "sector")


class PedidoInternoDetalleInline(admin.TabularInline):
    model = PedidoInternoDetalle
    extra = 0
    fields = (
        "tipo",
        "producto",
        "servicio",
        "descripcion",
        "cantidad",
        "observacion",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PedidoDestinoInline(admin.TabularInline):
    model = PedidoDestino
    extra = 0
    fields = (
        "sector_destino",
        "estado",
        "fecha_estado",
        "leido",
        "fecha_leido",
        "leido_por",
        "responsable",
        "observacion",
        "creado",
        "actualizado",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PedidoMovimientoInline(admin.TabularInline):
    model = PedidoMovimiento
    extra = 0
    fields = (
        "destino",
        "accion",
        "usuario",
        "estado_anterior",
        "estado_nuevo",
        "detalle",
        "sla_aplica",
        "sla_limite_horas",
        "sla_duracion_horas",
        "sla_vencido",
        "fecha",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PedidoInterno)
class PedidoInternoAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = (
        "numero",
        "fecha",
        "solicitante",
        "sector_origen",
        "estado",
        "prioridad",
        "creado",
    )
    list_filter = ("estado", "prioridad", "sector_origen", "fecha")
    search_fields = (
        "=numero",
        "solicitante__username",
        "solicitante__first_name",
        "solicitante__last_name",
        "sector_origen__codigo",
        "observaciones",
    )
    ordering = ("-id",)
    list_select_related = ("solicitante", "sector_origen")
    readonly_fields = (
        "numero",
        "fecha",
        "solicitante",
        "sector_origen",
        "estado",
        "prioridad",
        "observaciones",
        "creado",
        "actualizado",
    )
    inlines = (
        PedidoInternoDetalleInline,
        PedidoDestinoInline,
        PedidoMovimientoInline,
    )


@admin.register(PedidoInternoDetalle)
class PedidoInternoDetalleAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = ("pedido", "tipo", "descripcion", "cantidad")
    list_filter = ("tipo",)
    search_fields = ("pedido__numero", "descripcion", "observacion")
    list_select_related = ("pedido", "producto", "servicio")


@admin.register(PedidoDestino)
class PedidoDestinoAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = (
        "pedido",
        "sector_destino",
        "estado",
        "leido",
        "responsable",
        "fecha_estado",
        "actualizado",
    )
    list_filter = (
        "sector_destino",
        "estado",
        "leido",
        "responsable",
        "fecha_estado",
    )
    search_fields = (
        "pedido__numero",
        "sector_destino__codigo",
        "sector_destino__nombre",
        "responsable__username",
        "responsable__first_name",
        "responsable__last_name",
    )
    ordering = ("-creado",)
    list_select_related = (
        "pedido",
        "sector_destino",
        "responsable",
        "leido_por",
    )


@admin.register(PedidoMovimiento)
class PedidoMovimientoAdmin(SoloLecturaAdminMixin, admin.ModelAdmin):
    list_display = (
        "pedido",
        "destino",
        "accion",
        "usuario",
        "transicion",
        "sla_aplica",
        "sla_vencido",
        "fecha",
    )
    list_filter = (
        "accion",
        "sla_aplica",
        "sla_vencido",
        "fecha",
        "destino__sector_destino",
    )
    search_fields = (
        "pedido__numero",
        "destino__sector_destino__codigo",
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "detalle",
    )
    ordering = ("-fecha", "-id")
    list_select_related = (
        "pedido",
        "destino",
        "destino__sector_destino",
        "usuario",
    )

    @admin.display(description="Transición")
    def transicion(self, obj):
        if obj.estado_anterior or obj.estado_nuevo:
            return f"{obj.estado_anterior or '—'} → {obj.estado_nuevo or '—'}"
        return "—"


@admin.register(PedidoReglaSLA)
class PedidoReglaSLAAdmin(SinEliminacionAdminMixin, admin.ModelAdmin):
    list_display = (
        "sector",
        "transicion",
        "horas_limite",
        "activo",
        "actualizado",
    )
    list_filter = (
        "sector",
        "activo",
        "hito_origen",
        "hito_destino",
    )
    search_fields = ("sector__codigo", "sector__nombre")
    autocomplete_fields = ("sector",)
    ordering = ("sector__codigo", "hito_origen", "hito_destino")
    list_select_related = ("sector",)
    readonly_fields = ("creado", "actualizado")

    @admin.display(description="Transición")
    def transicion(self, obj):
        return (
            f"{obj.get_hito_origen_display()} → "
            f"{obj.get_hito_destino_display()}"
        )
