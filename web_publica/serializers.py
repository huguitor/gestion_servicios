# gestion/web_publica/serializers.py

from rest_framework import serializers
from productos.serializers import (
    ProductoWebPublicoSerializer,
    ServicioWebPublicoSerializer,
)
from configuracion.models import ConfiguracionGlobal


class EmpresaWebPublicaSerializer(serializers.ModelSerializer):
    logo_principal_url = serializers.SerializerMethodField()
    logo_favicon_url = serializers.SerializerMethodField()
    imagen_publicitaria_1_url = serializers.SerializerMethodField()
    imagen_publicitaria_2_url = serializers.SerializerMethodField()
    imagen_publicitaria_3_url = serializers.SerializerMethodField()

    class Meta:
        model = ConfiguracionGlobal
        fields = [
            "nombre_empresa",
            "nombre_fantasia",
            "descripcion_sistema",
            "direccion",
            "telefono",
            "email",
            "pagina_web",
            "logo_principal_url",
            "logo_favicon_url",
            "imagen_publicitaria_1_url",
            "imagen_publicitaria_2_url",
            "imagen_publicitaria_3_url",
        ]

    def _build_absolute_url(self, file_field):
        if file_field and hasattr(file_field, "url"):
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(file_field.url)
            return file_field.url
        return None

    def get_logo_principal_url(self, obj):
        return self._build_absolute_url(obj.logo_principal)

    def get_logo_favicon_url(self, obj):
        return self._build_absolute_url(obj.logo_favicon)

    def get_imagen_publicitaria_1_url(self, obj):
        return self._build_absolute_url(obj.imagen_publicitaria_1)

    def get_imagen_publicitaria_2_url(self, obj):
        return self._build_absolute_url(obj.imagen_publicitaria_2)

    def get_imagen_publicitaria_3_url(self, obj):
        return self._build_absolute_url(obj.imagen_publicitaria_3)


class HomeWebSerializer(serializers.Serializer):
    empresa = serializers.SerializerMethodField()
    productos_destacados = serializers.SerializerMethodField()
    servicios_destacados = serializers.SerializerMethodField()

    def get_empresa(self, obj):
        config = obj.get("config")
        if not config:
            return None

        serializer = EmpresaWebPublicaSerializer(
            config,
            context=self.context
        )
        return serializer.data

    def get_productos_destacados(self, obj):
        productos = obj.get("productos", [])
        serializer = ProductoWebPublicoSerializer(
            productos,
            many=True,
            context=self.context
        )
        return serializer.data

    def get_servicios_destacados(self, obj):
        servicios = obj.get("servicios", [])
        serializer = ServicioWebPublicoSerializer(
            servicios,
            many=True,
            context=self.context
        )
        return serializer.data