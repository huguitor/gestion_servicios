# gestion/backend/archivos/serializers.py

from rest_framework import serializers

from .models import (
    TipoArchivo,
    Archivo,
    ArchivoRelacion,
)


class TipoArchivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoArchivo
        fields = "__all__"


class ArchivoSerializer(serializers.ModelSerializer):
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
            "descripcion",

            "archivo",
            "archivo_url",

            "thumbnail",
            "thumbnail_url",

            "tipo",
            "tipo_nombre",

            "mime_type",
            "extension",

            "tamano_bytes",
            "tamano_kb",

            "checksum",

            "creado",
            "actualizado",
        ]

        read_only_fields = [
            "mime_type",
            "extension",
            "tamano_bytes",
            "checksum",
            "creado",
            "actualizado",
        ]

    def get_tamano_kb(self, obj):
        if not obj.tamano_bytes:
            return 0

        return round(obj.tamano_bytes / 1024, 2)

    def get_archivo_url(self, obj):
        request = self.context.get("request")

        if not obj.archivo:
            return None

        try:
            if request:
                return request.build_absolute_uri(obj.archivo.url)

            return obj.archivo.url

        except Exception:
            return None

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")

        if not obj.thumbnail:
            return None

        try:
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)

            return obj.thumbnail.url

        except Exception:
            return None


class ArchivoRelacionSerializer(serializers.ModelSerializer):
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
        