# gestion/backend/productos/serializers.py

from rest_framework import serializers
from .models import Producto, Servicio, ProductoImpuesto, ServicioImpuesto
from categorias.models import Categoria
from marcas.models import Marca
from proveedores.models import Proveedor
from impuestos.models import Impuesto
import json
import logging


# Configurar logger
logger = logging.getLogger(__name__)

def build_file_url(obj, field_name, request=None):
    archivo = getattr(obj, field_name, None)

    if archivo and hasattr(archivo, "url"):
        if request is not None:
            return request.build_absolute_uri(archivo.url)
        return archivo.url

    return None


# -----------------------------
# Serializer de impuestos
# -----------------------------
class ImpuestoDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Impuesto
        fields = ['id', 'nombre', 'porcentaje']


class ProductoImpuestoSerializer(serializers.ModelSerializer):
    impuesto = ImpuestoDetalleSerializer(read_only=True)
    impuesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Impuesto.objects.all(), source='impuesto', write_only=True
    )


    class Meta:
        model = ProductoImpuesto
        fields = ['id', 'impuesto', 'impuesto_id', 'tipo']


    def validate(self, data):
        """
        Asegura que el campo 'impuesto' no sea nulo
        """
        if not data.get('impuesto'):
            raise serializers.ValidationError("El campo 'impuesto' es obligatorio")
        return data


class ServicioImpuestoSerializer(serializers.ModelSerializer):
    impuesto = ImpuestoDetalleSerializer(read_only=True)
    impuesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Impuesto.objects.all(), source='impuesto', write_only=True
    )


    class Meta:
        model = ServicioImpuesto
        fields = ['id', 'impuesto', 'impuesto_id', 'tipo']


    def validate(self, data):
        """
        Asegura que el campo 'impuesto' no sea nulo
        """
        if not data.get('impuesto'):
            raise serializers.ValidationError("El campo 'impuesto' es obligatorio")
        return data


# -----------------------------
# Serializer de productos
# -----------------------------
class ProductoSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), allow_null=True, required=False)
    marca = serializers.PrimaryKeyRelatedField(queryset=Marca.objects.all(), allow_null=True, required=False)
    proveedor = serializers.PrimaryKeyRelatedField(queryset=Proveedor.objects.all(), allow_null=True, required=False)
    productoimpuesto_set = ProductoImpuestoSerializer(many=True, required=False)
    display_name = serializers.CharField(source='__str__', read_only=True)

    foto_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    plano_url = serializers.SerializerMethodField()
    multimedia = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            'id', 'sku', 'codigo_barras', 'nombre', 'descripcion',
            'precio_venta', 'costo_compra',
            'stock', 'proveedor', 'categoria', 'marca',
            'productoimpuesto_set',
            'foto', 'foto_url',
            'video', 'video_url',
            'plano', 'plano_url',
            'multimedia',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = [
            'creado', 'actualizado', 'sku', 'display_name',
            'foto_url', 'video_url', 'plano_url', 'multimedia'
        ]

    def get_foto_url(self, obj):
        return build_file_url(obj, "foto", self.context.get("request"))

    def get_video_url(self, obj):
        return build_file_url(obj, "video", self.context.get("request"))

    def get_plano_url(self, obj):
        return build_file_url(obj, "plano", self.context.get("request"))

    def get_multimedia(self, obj):
        tiene_foto = bool(obj.foto)
        tiene_video = bool(obj.video)
        tiene_plano = bool(obj.plano)

        return {
            "tiene_foto": tiene_foto,
            "tiene_video": tiene_video,
            "tiene_plano": tiene_plano,
            "total": sum([tiene_foto, tiene_video, tiene_plano]),
        }

    def to_internal_value(self, data):
        logger.debug(f"Datos recibidos en to_internal_value (Producto): {data}")

        if hasattr(data, 'getlist'):
            data_dict = {}

            for key in data:
                values = data.getlist(key)
                data_dict[key] = values[0] if len(values) == 1 else values

            data = data_dict

        if 'productoimpuesto_set' in data and isinstance(data['productoimpuesto_set'], str):
            try:
                data['productoimpuesto_set'] = json.loads(data['productoimpuesto_set'])
                logger.debug(f"productoimpuesto_set parseado: {data['productoimpuesto_set']}")
            except json.JSONDecodeError as e:
                logger.error(f"Error al parsear productoimpuesto_set: {str(e)}")
                raise serializers.ValidationError({
                    'productoimpuesto_set': 'Formato JSON inválido para productoimpuesto_set'
                })

        for field in ['codigo_barras', 'costo_compra', 'proveedor', 'categoria', 'marca']:
            if field in data and data[field] == '':
                data[field] = None

        for field in data:
            if data[field] == 'null':
                data[field] = None

        return super().to_internal_value(data)

    def validate(self, data):
        logger.debug(f"Datos validados (Producto): {data}")
        return super().validate(data)

    def create(self, validated_data):
        logger.debug(f"Creando producto con validated_data: {validated_data}")

        impuestos_data = validated_data.pop('productoimpuesto_set', [])
        logger.debug(f"Impuestos para crear: {impuestos_data}")

        for field in ['codigo_barras', 'costo_compra', 'proveedor', 'categoria', 'marca']:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = None

        producto = Producto.objects.create(**validated_data)

        for impuesto_data in impuestos_data:
            if impuesto_data.get('impuesto'):
                logger.debug(f"Creando ProductoImpuesto: {impuesto_data}")
                ProductoImpuesto.objects.create(producto=producto, **impuesto_data)

        return producto

    def update(self, instance, validated_data):
        logger.debug(f"Actualizando producto con validated_data: {validated_data}")

        impuestos_data = validated_data.pop('productoimpuesto_set', None)
        logger.debug(f"Impuestos para actualizar: {impuestos_data}")

        for field in ['codigo_barras', 'costo_compra', 'proveedor', 'categoria', 'marca']:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = None

        instance = super().update(instance, validated_data)

        if impuestos_data is not None:
            logger.debug("Eliminando impuestos existentes (Producto)")
            instance.productoimpuesto_set.all().delete()

            for impuesto_data in impuestos_data:
                if impuesto_data.get('impuesto'):
                    logger.debug(f"Creando ProductoImpuesto: {impuesto_data}")
                    ProductoImpuesto.objects.create(producto=instance, **impuesto_data)

        return instance


# -----------------------------
# Serializer de servicios
# -----------------------------
class ServicioSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), allow_null=True, required=False)
    marca = serializers.PrimaryKeyRelatedField(queryset=Marca.objects.all(), allow_null=True, required=False)
    servicioimpuesto_set = ServicioImpuestoSerializer(many=True, required=False)
    display_name = serializers.CharField(source='__str__', read_only=True)

    imagen_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    adjunto_url = serializers.SerializerMethodField()
    multimedia = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            'id', 'codigo_interno', 'nombre', 'descripcion',
            'costo_base', 'precio_base',
            'categoria', 'marca',
            'servicioimpuesto_set',
            'imagen', 'imagen_url',
            'video', 'video_url',
            'adjunto', 'adjunto_url',
            'multimedia',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = [
            'creado', 'actualizado', 'codigo_interno', 'display_name',
            'imagen_url', 'video_url', 'adjunto_url', 'multimedia'
        ]

    def get_imagen_url(self, obj):
        return build_file_url(obj, "imagen", self.context.get("request"))

    def get_video_url(self, obj):
        return build_file_url(obj, "video", self.context.get("request"))

    def get_adjunto_url(self, obj):
        return build_file_url(obj, "adjunto", self.context.get("request"))

    def get_multimedia(self, obj):
        tiene_imagen = bool(obj.imagen)
        tiene_video = bool(obj.video)
        tiene_adjunto = bool(obj.adjunto)

        return {
            "tiene_imagen": tiene_imagen,
            "tiene_video": tiene_video,
            "tiene_adjunto": tiene_adjunto,
            "total": sum([tiene_imagen, tiene_video, tiene_adjunto]),
        }

    def to_internal_value(self, data):
        logger.debug(f"Datos recibidos en to_internal_value (Servicio): {data}")

        if hasattr(data, 'getlist'):
            data_dict = {}

            for key in data:
                values = data.getlist(key)
                data_dict[key] = values[0] if len(values) == 1 else values

            data = data_dict

        if 'servicioimpuesto_set' in data and isinstance(data['servicioimpuesto_set'], str):
            try:
                data['servicioimpuesto_set'] = json.loads(data['servicioimpuesto_set'])
                logger.debug(f"servicioimpuesto_set parseado: {data['servicioimpuesto_set']}")
            except json.JSONDecodeError as e:
                logger.error(f"Error al parsear servicioimpuesto_set: {str(e)}")
                raise serializers.ValidationError({
                    'servicioimpuesto_set': 'Formato JSON inválido para servicioimpuesto_set'
                })

        for field in ['costo_base', 'precio_base', 'categoria', 'marca']:
            if field in data and data[field] == '':
                data[field] = None

        for field in data:
            if data[field] == 'null':
                data[field] = None

        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        representation['precio_base'] = representation['precio_base'] or 0.0
        representation['costo_base'] = representation['costo_base'] or 0.0

        representation['servicioimpuesto_set'] = [
            imp for imp in representation['servicioimpuesto_set']
            if imp.get('impuesto')
        ]

        return representation

    def create(self, validated_data):
        logger.debug(f"Creando servicio con validated_data: {validated_data}")

        impuestos_data = validated_data.pop('servicioimpuesto_set', [])
        logger.debug(f"Impuestos para crear (Servicio): {impuestos_data}")

        for field in ['costo_base', 'precio_base', 'categoria', 'marca']:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = None

        servicio = Servicio.objects.create(**validated_data)

        for impuesto_data in impuestos_data:
            if impuesto_data.get('impuesto'):
                logger.debug(f"Creando ServicioImpuesto: {impuesto_data}")
                ServicioImpuesto.objects.create(servicio=servicio, **impuesto_data)

        return servicio

    def update(self, instance, validated_data):
        logger.debug(f"Actualizando servicio con validated_data: {validated_data}")

        impuestos_data = validated_data.pop('servicioimpuesto_set', None)
        logger.debug(f"Impuestos para actualizar (Servicio): {impuestos_data}")

        for field in ['costo_base', 'precio_base', 'categoria', 'marca']:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = None

        instance = super().update(instance, validated_data)

        if impuestos_data is not None:
            logger.debug("Eliminando impuestos existentes (Servicio)")
            instance.servicioimpuesto_set.all().delete()

            for impuesto_data in impuestos_data:
                if impuesto_data.get('impuesto'):
                    logger.debug(f"Creando ServicioImpuesto: {impuesto_data}")
                    ServicioImpuesto.objects.create(servicio=instance, **impuesto_data)

        return instance

class ProductoWebPublicoSerializer(serializers.ModelSerializer):
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion_corta",
            "foto_url",
            "precio_venta",
        ]

    def get_foto_url(self, obj):
        if obj.foto and hasattr(obj.foto, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.foto.url)
            return obj.foto.url
        return None

class ProductoWebHomeSerializer(serializers.ModelSerializer):
    foto_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion_corta",
            "foto_url",
            "video_url",
        ]

    def get_foto_url(self, obj):
        if obj.foto and hasattr(obj.foto, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.foto.url)
            return obj.foto.url
        return None

    def get_video_url(self, obj):
        if obj.video and hasattr(obj.video, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        return None

class ProductoWebClienteSerializer(serializers.ModelSerializer):

    foto_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    stock_disponible = serializers.SerializerMethodField()


    class Meta:
        model = Producto

        fields = [
            "id",
            "sku",
            "nombre",
            "slug",
            "descripcion_corta",
            "foto_url",
            "video_url",
            "precio_venta",
            "stock_disponible",
        ]


    def get_stock_disponible(self, obj):
        return obj.stock_disponible


    def get_foto_url(self, obj):

        if obj.foto and hasattr(obj.foto, "url"):

            request = self.context.get("request")

            if request:
                return request.build_absolute_uri(obj.foto.url)

            return obj.foto.url

        return None


    def get_video_url(self, obj):

        if obj.video and hasattr(obj.video, "url"):

            request = self.context.get("request")

            if request:
                return request.build_absolute_uri(obj.video.url)

            return obj.video.url

        return None

class ProductoWebDetalleSerializer(serializers.ModelSerializer):
    foto_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    categoria_nombre = serializers.SerializerMethodField()
    marca_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion",
            "descripcion_corta",
            "foto_url",
            "video_url",
            "categoria_nombre",
            "marca_nombre",
        ]

    def get_foto_url(self, obj):
        if obj.foto and hasattr(obj.foto, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.foto.url)
            return obj.foto.url
        return None

    def get_video_url(self, obj):
        if obj.video and hasattr(obj.video, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        return None

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else ""

    def get_marca_nombre(self, obj):
        return obj.marca.nombre if obj.marca else ""

class ProductoWebClienteDetalleSerializer(serializers.ModelSerializer):

    foto_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    categoria_nombre = serializers.SerializerMethodField()
    marca_nombre = serializers.SerializerMethodField()

    stock_disponible = serializers.SerializerMethodField()


    class Meta:
        model = Producto

        fields = [
            "id",
            "sku",
            "nombre",
            "slug",
            "descripcion",
            "descripcion_corta",
            "foto_url",
            "video_url",
            "precio_venta",
            "stock_disponible",
            "categoria_nombre",
            "marca_nombre",
        ]


    def get_stock_disponible(self, obj):
        return obj.stock_disponible


    def get_foto_url(self, obj):

        if obj.foto and hasattr(obj.foto, "url"):

            request = self.context.get("request")

            if request:
                return request.build_absolute_uri(obj.foto.url)

            return obj.foto.url

        return None


    def get_video_url(self, obj):

        if obj.video and hasattr(obj.video, "url"):

            request = self.context.get("request")

            if request:
                return request.build_absolute_uri(obj.video.url)

            return obj.video.url

        return None


    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else ""


    def get_marca_nombre(self, obj):
        return obj.marca.nombre if obj.marca else ""
class ServicioWebPublicoSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion_corta",
            "imagen_url",
            "video_url",
            "precio_base",
        ]

    def get_imagen_url(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None

    def get_video_url(self, obj):
        if obj.video and hasattr(obj.video, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        return None

class ServicioWebDetalleSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    categoria_nombre = serializers.SerializerMethodField()
    marca_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion",
            "descripcion_corta",
            "imagen_url",
            "video_url",
            "categoria_nombre",
            "marca_nombre",
        ]

    def get_imagen_url(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None

    def get_video_url(self, obj):
        if obj.video and hasattr(obj.video, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        return None

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else ""

    def get_marca_nombre(self, obj):
        return obj.marca.nombre if obj.marca else ""
class ServicioWebClienteSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            "id",
            "codigo_interno",
            "nombre",
            "slug",
            "descripcion_corta",
            "imagen_url",
            "video_url",
            "precio_base",
        ]

    def get_imagen_url(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None

    def get_video_url(self, obj):
        if obj.video and hasattr(obj.video, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        return None


class ServicioWebClienteDetalleSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    categoria_nombre = serializers.SerializerMethodField()
    marca_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            "id",
            "codigo_interno",
            "nombre",
            "slug",
            "descripcion",
            "descripcion_corta",
            "imagen_url",
            "video_url",
            "precio_base",
            "categoria_nombre",
            "marca_nombre",
        ]

    def get_imagen_url(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None

    def get_video_url(self, obj):
        if obj.video and hasattr(obj.video, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.video.url)
            return obj.video.url
        return None

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else ""

    def get_marca_nombre(self, obj):
        return obj.marca.nombre if obj.marca else ""