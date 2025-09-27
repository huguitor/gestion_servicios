# gestion/impuestos/admin.py
from django.contrib import admin
from .models import Impuesto

@admin.register(Impuesto)
class ImpuestoAdmin(admin.ModelAdmin):
    search_fields = ['nombre']  # <- esto permite que autocomplete funcione
