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
    
    # ✅ NUEVO CAMPO - URL completa de la foto
    foto_url = serializers.SerializerMethodField()


    class Meta:
        model = Producto
        fields = [
            'id', 'sku', 'codigo_barras', 'nombre', 'descripcion', 'precio_venta', 'costo_compra',
            'stock', 'proveedor', 'categoria', 'marca', 'productoimpuesto_set', 'foto', 'foto_url', 'plano',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = ['creado', 'actualizado', 'sku', 'display_name', 'foto_url']  # ✅ Agregar foto_url aquí


    # ✅ NUEVO MÉTODO - Obtener URL completa de la foto
    def get_foto_url(self, obj):
        """Devuelve la URL completa de la foto"""
        if obj.foto and hasattr(obj.foto, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.foto.url)
            return obj.foto.url
        return None


    def to_internal_value(self, data):
        """
        Convierte strings vacíos a None para campos opcionales y maneja productoimpuesto_set como JSON
        """
        logger.debug(f"Datos recibidos en to_internal_value (Producto): {data}")


        # Si data es FormData, convertir a dict primero
        if hasattr(data, 'getlist'):
            data_dict = {}
            for key in data:
                values = data.getlist(key)
                if len(values) == 1:
                    data_dict[key] = values[0]
                else:
                    data_dict[key] = values
            data = data_dict


        # Manejar productoimpuesto_set como JSON
        if 'productoimpuesto_set' in data and isinstance(data['productoimpuesto_set'], str):
            try:
                data['productoimpuesto_set'] = json.loads(data['productoimpuesto_set'])
                logger.debug(f"productoimpuesto_set parseado: {data['productoimpuesto_set']}")
            except json.JSONDecodeError as e:
                logger.error(f"Error al parsear productoimpuesto_set: {str(e)}")
                raise serializers.ValidationError({
                    'productoimpuesto_set': 'Formato JSON inválido para productoimpuesto_set'
                })


        # Convertir strings vacíos a None
        for field in ['codigo_barras', 'costo_compra', 'proveedor', 'categoria', 'marca']:
            if field in data and data[field] == '':
                data[field] = None


        # Convertir 'null' string a None
        for field in data:
            if data[field] == 'null':
                data[field] = None


        return super().to_internal_value(data)


    def validate(self, data):
        """
        Validar datos antes de guardar
        """
        logger.debug(f"Datos validados (Producto): {data}")
        return super().validate(data)


    def create(self, validated_data):
        logger.debug(f"Creando producto con validated_data: {validated_data}")
        impuestos_data = validated_data.pop('productoimpuesto_set', [])
        logger.debug(f"Impuestos para crear: {impuestos_data}")


        # Asegurar que los campos opcionales sean None si no tienen valor
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
        impuestos_data = validated_data.pop('productoimpuesto_set', [])
        logger.debug(f"Impuestos para actualizar: {impuestos_data}")


        # Asegurar que los campos opcionales sean None si no tienen valor
        for field in ['codigo_barras', 'costo_compra', 'proveedor', 'categoria', 'marca']:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = None


        instance = super().update(instance, validated_data)
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
    
    # ✅ NUEVO CAMPO - URL completa de la imagen
    imagen_url = serializers.SerializerMethodField()


    class Meta:
        model = Servicio
        fields = [
            'id', 'codigo_interno', 'nombre', 'descripcion', 'costo_base', 'precio_base',
            'categoria', 'marca', 'servicioimpuesto_set', 'imagen', 'imagen_url', 'adjunto',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = ['creado', 'actualizado', 'codigo_interno', 'display_name', 'imagen_url']  # ✅ Agregar imagen_url aquí


    # ✅ NUEVO MÉTODO - Obtener URL completa de la imagen
    def get_imagen_url(self, obj):
        """Devuelve la URL completa de la imagen"""
        if obj.imagen and hasattr(obj.imagen, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None


    def to_internal_value(self, data):
        """
        Convierte strings vacíos a None para campos opcionales y maneja servicioimpuesto_set como JSON
        """
        logger.debug(f"Datos recibidos en to_internal_value (Servicio): {data}")


        # Si data es FormData, convertir a dict primero
        if hasattr(data, 'getlist'):
            data_dict = {}
            for key in data:
                values = data.getlist(key)
                if len(values) == 1:
                    data_dict[key] = values[0]
                else:
                    data_dict[key] = values
            data = data_dict


        # Manejar servicioimpuesto_set como JSON
        if 'servicioimpuesto_set' in data and isinstance(data['servicioimpuesto_set'], str):
            try:
                data['servicioimpuesto_set'] = json.loads(data['servicioimpuesto_set'])
                logger.debug(f"servicioimpuesto_set parseado: {data['servicioimpuesto_set']}")
            except json.JSONDecodeError as e:
                logger.error(f"Error al parsear servicioimpuesto_set: {str(e)}")
                raise serializers.ValidationError({
                    'servicioimpuesto_set': 'Formato JSON inválido para servicioimpuesto_set'
                })


        # Convertir strings vacíos a None
        for field in ['costo_base', 'precio_base', 'categoria', 'marca']:
            if field in data and data[field] == '':
                data[field] = None


        # Convertir 'null' string a None
        for field in data:
            if data[field] == 'null':
                data[field] = None


        return super().to_internal_value(data)


    def to_representation(self, instance):
        """
        Asegura que precio_base y costo_base nunca se devuelvan como null
        """
        representation = super().to_representation(instance)
        representation['precio_base'] = representation['precio_base'] or 0.0
        representation['costo_base'] = representation['costo_base'] or 0.0
        # Filtrar servicioimpuesto_set para excluir impuestos nulos
        representation['servicioimpuesto_set'] = [
            imp for imp in representation['servicioimpuesto_set'] if imp.get('impuesto')
        ]
        return representation


    def create(self, validated_data):
        logger.debug(f"Creando servicio con validated_data: {validated_data}")
        impuestos_data = validated_data.pop('servicioimpuesto_set', [])
        logger.debug(f"Impuestos para crear (Servicio): {impuestos_data}")


        # Asegurar que los campos opcionales sean None si no tienen valor
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
        impuestos_data = validated_data.pop('servicioimpuesto_set', [])
        logger.debug(f"Impuestos para actualizar (Servicio): {impuestos_data}")


        # Asegurar que los campos opcionales sean None si no tienen valor
        for field in ['costo_base', 'precio_base', 'categoria', 'marca']:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = None


        instance = super().update(instance, validated_data)
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


class ProductoWebDetalleSerializer(serializers.ModelSerializer):
    foto_url = serializers.SerializerMethodField()
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
            "precio_venta",
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

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else ""

    def get_marca_nombre(self, obj):
        return obj.marca.nombre if obj.marca else ""


class ServicioWebPublicoSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            "id",
            "nombre",
            "slug",
            "descripcion_corta",
            "imagen_url",
            "precio_base",
        ]

    def get_imagen_url(self, obj):
        if obj.imagen and hasattr(obj.imagen, 'url'):
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None


class ServicioWebDetalleSerializer(serializers.ModelSerializer):
    imagen_url = serializers.SerializerMethodField()
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

    def get_categoria_nombre(self, obj):
        return obj.categoria.nombre if obj.categoria else ""

    def get_marca_nombre(self, obj):
        return obj.marca.nombre if obj.marca else ""