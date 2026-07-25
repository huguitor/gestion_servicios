# gestion/clientes/admin.py

from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "documento", "plazo_cobro_dias", "activo")
    search_fields = ("nombre", "apellido", "documento")
    list_filter = ("activo", "tipo", "condicion_iva")
