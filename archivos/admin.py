# gestion/backend/archivos/admin.py

from django.contrib import admin

from .models import (
    TipoArchivo,
    Archivo,
    ArchivoRelacion,
)


@admin.register(TipoArchivo)
class TipoArchivoAdmin(admin.ModelAdmin):

    list_display = (
        "nombre",
        "icono",
        "activo",
    )

    list_filter = (
        "activo",
    )

    search_fields = (
        "nombre",
        "descripcion",
    )

    ordering = (
        "nombre",
    )


@admin.register(Archivo)
class ArchivoAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "nombre",
        "tipo",
        "extension",
        "mime_type",
        "tamano_bytes",
        "creado",
    )

    list_filter = (
        "tipo",
        "extension",
        "mime_type",
        "creado",
    )

    search_fields = (
        "nombre",
        "descripcion",
        "checksum",
    )

    readonly_fields = (
        "mime_type",
        "extension",
        "tamano_bytes",
        "checksum",
        "creado",
        "actualizado",
    )

    ordering = (
        "-creado",
    )


@admin.register(ArchivoRelacion)
class ArchivoRelacionAdmin(admin.ModelAdmin):

    list_display = (
        "archivo",
        "content_type",
        "object_id",
        "rol",
        "orden",
        "creado",
    )

    list_filter = (
        "content_type",
        "rol",
    )

    search_fields = (
        "archivo__nombre",
        "object_id",
    )

    ordering = (
        "orden",
        "-creado",
    )
    