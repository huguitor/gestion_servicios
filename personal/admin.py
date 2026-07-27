from django.contrib import admin

from .access import puede_acceder_administracion, puede_acceder_pedidos_internos
from .models import Cargo, Empleado, RolPersonal
from .services import asignar_rol


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "legajo", "rol", "cargo", "activo", "acceso_admin", "acceso_operativo"]
    list_filter = ["activo", "rol", "cargo"]
    search_fields = ["usuario__username", "usuario__first_name", "usuario__last_name", "usuario__email", "legajo", "documento"]
    autocomplete_fields = ["usuario", "rol", "cargo"]

    @admin.display(boolean=True, description="Administración")
    def acceso_admin(self, obj):
        return puede_acceder_administracion(obj.usuario)

    @admin.display(boolean=True, description="Pedidos internos")
    def acceso_operativo(self, obj):
        return puede_acceder_pedidos_internos(obj.usuario)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        rol = obj.rol
        if not obj.pk:
            obj.rol = None
            super().save_model(request, obj, form, change)
        asignar_rol(empleado=obj, rol=rol)
        obj.rol = rol
        super().save_model(request, obj, form, change)


@admin.register(RolPersonal)
class RolPersonalAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "grupo", "activo", "orden"]
    list_filter = ["activo"]
    search_fields = ["codigo", "nombre", "grupo__name"]
    autocomplete_fields = ["grupo"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "activo"]
    list_filter = ["activo"]
    search_fields = ["codigo", "nombre"]

    def has_delete_permission(self, request, obj=None):
        return False
