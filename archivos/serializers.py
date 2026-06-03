# gestion/backend/archivos/serializers.py

import os

from django.conf import settings

from rest_framework import serializers

from .models import (
    TipoArchivo,
    Archivo,
    ArchivoRelacion,
)


class TipoArchivoSerializer(serializers.ModelSerializer):
    """
    Serializer para el catálogo de tipos de archivos.
    """

    class Meta:
        model = TipoArchivo
        fields = "__all__"


class ArchivoSerializer(serializers.ModelSerializer):
    """
    Serializer principal del repositorio de archivos.

    Incluye:
    - URLs absolutas para archivo y thumbnail.
    - Tamaño en KB.
    - Nombre del tipo.
    - Validaciones de tamaño y extensión.
    """

    tamano_kb = serializers.SerializerMethodField()

    archivo_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    tipo_nombre = serializers.CharField(
        source="tipo.nombre",
        read_only=True
    )

    class Meta:
        model = Archivo

        fields = [
            "id",

            "nombre",
            "nombre_original",
            "descripcion",

            "archivo",
            "archivo_url",

            "thumbnail",
            "thumbnail_url",

            "tipo",
            "tipo_nombre",

            "activo",

            "mime_type",
            "extension",

            "tamano_bytes",
            "tamano_kb",

            "checksum",

            "creado",
            "actualizado",
        ]

        read_only_fields = [
            "nombre_original",

            "mime_type",
            "extension",

            "tamano_bytes",
            "checksum",

            "creado",
            "actualizado",
        ]

    # ==================================================
    # VALIDACIONES
    # ==================================================

    def validate_archivo(self, value):
        """
        Valida:

        - Tamaño máximo
        - Extensión permitida

        La validación de MIME real se agregará
        posteriormente usando python-magic.
        """

        if not value:
            return value

        # ----------------------------------------------
        # Tamaño máximo
        # ----------------------------------------------

        max_size = (
            settings.ARCHIVOS_MAX_MB
            * 1024
            * 1024
        )

        if value.size > max_size:
            raise serializers.ValidationError(
                (
                    f"El archivo supera el límite "
                    f"de {settings.ARCHIVOS_MAX_MB} MB."
                )
            )

        # ----------------------------------------------
        # Extensión
        # ----------------------------------------------

        extension = (
            os.path.splitext(value.name)[1]
            .lower()
            .replace(".", "")
        )

        extensiones_permitidas = set()

        for grupo in settings.EXTENSIONES_PERMITIDAS.values():
            extensiones_permitidas.update(grupo)

        if extension not in extensiones_permitidas:
            raise serializers.ValidationError(
                (
                    f"Extensión no permitida: "
                    f".{extension}"
                )
            )

        return value

    # ==================================================
    # CAMPOS CALCULADOS
    # ==================================================

    def get_tamano_kb(self, obj):
        """
        Devuelve tamaño en KB.
        """

        if not obj.tamano_bytes:
            return 0

        return round(
            obj.tamano_bytes / 1024,
            2
        )

    def get_archivo_url(self, obj):
        """
        Devuelve URL absoluta del archivo.
        """

        request = self.context.get("request")

        if not obj.archivo:
            return None

        try:

            if request:
                return request.build_absolute_uri(
                    obj.archivo.url
                )

            return obj.archivo.url

        except Exception:
            return None

    def get_thumbnail_url(self, obj):
        """
        Devuelve URL absoluta del thumbnail.
        """

        request = self.context.get("request")

        if not obj.thumbnail:
            return None

        try:

            if request:
                return request.build_absolute_uri(
                    obj.thumbnail.url
                )

            return obj.thumbnail.url

        except Exception:
            return None


class ArchivoRelacionSerializer(serializers.ModelSerializer):
    """
    Serializer para relaciones polimórficas.

    Permite asociar archivos a cualquier
    entidad del sistema mediante GenericForeignKey.
    """

    archivo_detalle = ArchivoSerializer(
        source="archivo",
        read_only=True
    )

    class Meta:
        model = ArchivoRelacion

        fields = [
            "id",

            "archivo",
            "archivo_detalle",

            "content_type",
            "object_id",

            "rol",
            "orden",
            "observaciones",

            "creado",
        ]

        read_only_fields = [
            "creado",
        ]