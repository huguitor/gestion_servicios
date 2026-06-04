# gestion/backend/archivos/serializers.py

from rest_framework import serializers

from django.contrib.contenttypes.models import ContentType

from .models import (
    TipoArchivo,
    Archivo,
    ArchivoRelacion,
)
from .services import FileStorage

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
            # El archivo y su metadata SOLO se crean vía
            # FileService.upload(). Este serializer es de lectura
            # para esos campos; nunca persiste ni analiza archivos.
            "archivo",
            "thumbnail",

            "nombre_original",

            "mime_type",
            "extension",

            "tamano_bytes",
            "checksum",

            "creado",
            "actualizado",
        ]

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
        Obtiene URL del archivo vía FileStorage.
        
        IMPORTANTE: No usa obj.archivo.url directamente.
        Va a través de FileStorage para respetar la abstracción.
        
        Si mañana cambias a S3/MinIO, esto funciona automático.
        """

        if not obj.archivo:
            return None

        try:
            # Usar FileStorage, no obj.archivo.url
            url = FileStorage.url(obj.archivo.name)

            # Si tenemos request, hacer URL absoluta
            request = self.context.get("request")
            if request and url:
                return request.build_absolute_uri(url)

            return url

        except Exception:
            return None

    def get_thumbnail_url(self, obj):
        """
        Obtiene URL del thumbnail vía FileStorage.
        
        IMPORTANTE: No usa obj.thumbnail.url directamente.
        Va a través de FileStorage para respetar la abstracción.
        """

        if not obj.thumbnail:
            return None

        try:
            # Usar FileStorage, no obj.thumbnail.url
            url = FileStorage.url(obj.thumbnail.name)

            # Si tenemos request, hacer URL absoluta
            request = self.context.get("request")
            if request and url:
                return request.build_absolute_uri(url)

            return url

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

class ArchivoUploadSimpleSerializer(serializers.Serializer):
    """
    Serializer de INPUT para el endpoint upload_simple.
    
    Solo VALIDA que los datos de entrada sean correctos.
    
    La lógica de crear Archivo + ArchivoRelacion está en
    FileService.upload() que es el punto único.
    
    Esto es una capa de validación de inputs solamente.
    """

    archivo = serializers.FileField()
    tipo = serializers.PrimaryKeyRelatedField(
        queryset=TipoArchivo.objects.all()
    )

    content_type = serializers.CharField(required=False, allow_blank=True)
    object_id = serializers.IntegerField(required=False)

    rol = serializers.CharField(required=False, default="principal")
    observaciones = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """
        Valida que los datos de entrada sean coherentes.
        
        Si hay content_type, debe haber object_id.
        El content_type debe existir en BD.
        """

        content_type_str = attrs.get("content_type", "").strip()
        object_id = attrs.get("object_id")

        # Si hay content_type, debe haber object_id
        if content_type_str and not object_id:
            raise serializers.ValidationError(
                {"object_id": "Requerido si especificas content_type"}
            )

        # Si content_type especificado, verificar que exista
        if content_type_str:
            try:
                content_type_obj = ContentType.objects.get(
                    model=content_type_str
                )
                attrs["content_type_obj"] = content_type_obj
            except ContentType.DoesNotExist:
                raise serializers.ValidationError(
                    {"content_type": f"Modelo no existe: {content_type_str}"}
                )
        else:
            attrs["content_type_obj"] = None

        return attrs