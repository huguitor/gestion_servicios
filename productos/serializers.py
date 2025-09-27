# gestion/productos/serializers.py
from rest_framework import serializers
from .models import Producto, Servicio, ProductoImpuesto, ServicioImpuesto
from categorias.models import Categoria
from marcas.models import Marca
from proveedores.models import Proveedor
from impuestos.models import Impuesto

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

class ServicioImpuestoSerializer(serializers.ModelSerializer):
    impuesto = ImpuestoDetalleSerializer(read_only=True)
    impuesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Impuesto.objects.all(), source='impuesto', write_only=True
    )

    class Meta:
        model = ServicioImpuesto
        fields = ['id', 'impuesto', 'impuesto_id', 'tipo']

# -----------------------------
# Serializer de productos
# -----------------------------
class ProductoSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), allow_null=True)
    marca = serializers.PrimaryKeyRelatedField(queryset=Marca.objects.all(), allow_null=True)
    proveedor = serializers.PrimaryKeyRelatedField(queryset=Proveedor.objects.all(), allow_null=True)
    productoimpuesto_set = ProductoImpuestoSerializer(many=True, required=False)
    display_name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id', 'sku', 'codigo_barras', 'nombre', 'descripcion', 'precio_venta', 'costo_compra',
            'stock', 'proveedor', 'categoria', 'marca', 'productoimpuesto_set', 'foto', 'plano',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = ['creado', 'actualizado', 'sku', 'display_name']

    def create(self, validated_data):
        impuestos_data = validated_data.pop('productoimpuesto_set', [])
        producto = Producto.objects.create(**validated_data)
        for impuesto_data in impuestos_data:
            ProductoImpuesto.objects.create(producto=producto, **impuesto_data)
        return producto

    def update(self, instance, validated_data):
        impuestos_data = validated_data.pop('productoimpuesto_set', [])
        instance = super().update(instance, validated_data)
        if impuestos_data:
            instance.productoimpuesto_set.all().delete()
            for impuesto_data in impuestos_data:
                ProductoImpuesto.objects.create(producto=instance, **impuesto_data)
        return instance

# -----------------------------
# Serializer de servicios
# -----------------------------
class ServicioSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all(), allow_null=True)
    marca = serializers.PrimaryKeyRelatedField(queryset=Marca.objects.all(), allow_null=True)
    servicioimpuesto_set = ServicioImpuestoSerializer(many=True, required=False)
    display_name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Servicio
        fields = [
            'id', 'codigo_interno', 'nombre', 'descripcion', 'costo_base', 'precio_base',
            'categoria', 'marca', 'servicioimpuesto_set', 'imagen', 'adjunto',
            'activo', 'creado', 'actualizado', 'display_name'
        ]
        read_only_fields = ['creado', 'actualizado', 'codigo_interno', 'display_name']

    def create(self, validated_data):
        impuestos_data = validated_data.pop('servicioimpuesto_set', [])
        servicio = Servicio.objects.create(**validated_data)
        for impuesto_data in impuestos_data:
            ServicioImpuesto.objects.create(servicio=servicio, **impuesto_data)
        return servicio

    def update(self, instance, validated_data):
        impuestos_data = validated_data.pop('servicioimpuesto_set', [])
        instance = super().update(instance, validated_data)
        if impuestos_data:
            instance.servicioimpuesto_set.all().delete()
            for impuesto_data in impuestos_data:
                ServicioImpuesto.objects.create(servicio=instance, **impuesto_data)
        return instance
