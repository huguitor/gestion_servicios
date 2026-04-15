# gestion_servicios/web_clientes/admin.py
from django.contrib import admin

from .models import ClienteWeb


@admin.register(ClienteWeb)
class ClienteWebAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "cliente",
        "activo",
        "email_verificado",
        "acepta_terminos",
        "fecha_alta",
        "ultimo_acceso",
    )
    list_filter = (
        "activo",
        "email_verificado",
        "acepta_terminos",
        "fecha_alta",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "cliente__nombre",
        "cliente__apellido",
        "cliente__documento",
    )
    ordering = ("-id",)