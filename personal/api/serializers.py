from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import serializers

from pedidos_internos.models import UsuarioSector
from personal.access import puede_acceder_administracion, puede_acceder_pedidos_internos
from personal.models import Cargo, Empleado, RolPersonal
from personal.services import asignar_rol


class RolPersonalSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source="grupo.name", read_only=True)

    class Meta:
        model = RolPersonal
        fields = ["id", "codigo", "nombre", "descripcion", "grupo", "grupo_nombre", "activo", "orden", "creado", "actualizado"]
        read_only_fields = ["id", "creado", "actualizado"]

    def validate_codigo(self, value):
        return value.strip().upper()


class CargoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cargo
        fields = ["id", "codigo", "nombre", "descripcion", "activo", "creado", "actualizado"]
        read_only_fields = ["id", "creado", "actualizado"]

    def validate_codigo(self, value):
        return value.strip().upper()


class EmpleadoSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="usuario.username", read_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    nombre_completo = serializers.SerializerMethodField()
    rol_codigo = serializers.CharField(source="rol.codigo", read_only=True, allow_null=True)
    rol_nombre = serializers.CharField(source="rol.nombre", read_only=True, allow_null=True)
    cargo_nombre = serializers.CharField(source="cargo.nombre", read_only=True, allow_null=True)
    sectores = serializers.SerializerMethodField()
    puede_acceder_administracion = serializers.SerializerMethodField()
    puede_acceder_pedidos_internos = serializers.SerializerMethodField()

    class Meta:
        model = Empleado
        fields = ["id", "usuario", "username", "first_name", "last_name", "email", "nombre_completo", "legajo", "documento", "fecha_ingreso", "activo", "rol", "rol_codigo", "rol_nombre", "cargo", "cargo_nombre", "observaciones", "sectores", "puede_acceder_administracion", "puede_acceder_pedidos_internos", "creado", "actualizado"]
        read_only_fields = ["id", "creado", "actualizado"]

    def validate_usuario(self, value):
        if self.instance and value.pk != self.instance.usuario_id:
            raise serializers.ValidationError("El usuario asociado a un empleado no puede modificarse.")
        if hasattr(value, "cliente_web"):
            raise serializers.ValidationError("Un cliente web no puede convertirse en empleado desde esta API.")
        return value

    def validate_legajo(self, value):
        return value.strip() or None if value else None

    def validate_documento(self, value):
        return value.strip() or None if value else None

    def get_nombre_completo(self, obj):
        return obj.usuario.get_full_name().strip() or obj.usuario.get_username()

    def get_sectores(self, obj):
        membresias = UsuarioSector.objects.filter(usuario=obj.usuario).select_related("sector").order_by("-principal", "sector__nombre")
        return [{"id": item.sector_id, "codigo": item.sector.codigo, "nombre": item.sector.nombre, "principal": item.principal, "activo": item.activo and item.sector.activo} for item in membresias]

    def get_puede_acceder_administracion(self, obj):
        return puede_acceder_administracion(obj.usuario)

    def get_puede_acceder_pedidos_internos(self, obj):
        return puede_acceder_pedidos_internos(obj.usuario)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["first_name"] = instance.usuario.first_name
        data["last_name"] = instance.usuario.last_name
        data["email"] = instance.usuario.email
        return data

    @staticmethod
    def _actualizar_datos_personales(usuario, validated_data):
        campos = []
        for field in ("first_name", "last_name", "email"):
            if field in validated_data:
                setattr(usuario, field, validated_data.pop(field))
                campos.append(field)
        if campos:
            usuario.save(update_fields=campos)

    @transaction.atomic
    def create(self, validated_data):
        usuario = validated_data["usuario"]
        self._actualizar_datos_personales(usuario, validated_data)
        rol = validated_data.pop("rol", None)
        empleado = Empleado.objects.create(rol=None, **validated_data)
        return asignar_rol(empleado=empleado, rol=rol)

    @transaction.atomic
    def update(self, instance, validated_data):
        self._actualizar_datos_personales(instance.usuario, validated_data)
        rol = validated_data.pop("rol", instance.rol)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return asignar_rol(empleado=instance, rol=rol)


class UsuarioInternoSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "first_name", "last_name", "nombre_completo", "is_staff", "is_active"]

    def get_nombre_completo(self, obj):
        return obj.get_full_name().strip() or obj.get_username()


class GrupoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]
