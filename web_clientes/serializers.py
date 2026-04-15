# gestion_servicios/web_clientes/serializers.py
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers

from clientes.models import Cliente
from .models import ClienteWeb


class RegistroClienteWebSerializer(serializers.Serializer):
    """
    Serializer de entrada para registro de cliente web.
    Se usa solo para validar y crear objetos.
    No se usa para serializar la respuesta.
    """

    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    acepta_terminos = serializers.BooleanField()

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este email ya está registrado.")

        return value

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_apellido(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El apellido es obligatorio.")
        return value

    def validate_telefono(self, value):
        return value.strip()

    def validate_acepta_terminos(self, value):
        if not value:
            raise serializers.ValidationError("Debe aceptar los términos.")
        return value

    def create(self, validated_data):
        nombre = validated_data["nombre"]
        apellido = validated_data["apellido"]
        email = validated_data["email"]
        password = validated_data["password"]
        telefono = validated_data.get("telefono", "")
        acepta_terminos = validated_data["acepta_terminos"]

        # Crear usuario Django
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=nombre,
            last_name=apellido,
        )

        # Crear cliente comercial
        cliente = Cliente.objects.create(
            nombre=nombre,
            apellido=apellido,
            email=email,
        )

        # Crear perfil web
        cliente_web = ClienteWeb.objects.create(
            user=user,
            cliente=cliente,
            telefono=telefono,
            acepta_terminos=acepta_terminos,
        )

        return cliente_web


class LoginClienteWebSerializer(serializers.Serializer):
    """
    Serializer de entrada para login de cliente web.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email", "").strip().lower()
        password = data.get("password")

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError("Credenciales inválidas.")

        if not hasattr(user, "cliente_web"):
            raise serializers.ValidationError("Usuario no tiene perfil web.")

        if not user.cliente_web.activo:
            raise serializers.ValidationError("El usuario web está inactivo.")

        data["user"] = user
        data["cliente_web"] = user.cliente_web

        return data


class ClienteWebSerializer(serializers.ModelSerializer):
    """
    Serializer de salida para perfil web.
    """

    nombre = serializers.CharField(source="user.first_name", read_only=True)
    apellido = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ClienteWeb
        fields = [
            "id",
            "nombre",
            "apellido",
            "email",
            "telefono",
            "activo",
            "email_verificado",
            "acepta_terminos",
            "fecha_alta",
        ]
        read_only_fields = fields

class ActualizarClienteWebSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="user.first_name", max_length=100)
    apellido = serializers.CharField(source="user.last_name", max_length=100)

    class Meta:
        model = ClienteWeb
        fields = [
            "nombre",
            "apellido",
            "telefono",
        ]

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_apellido(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El apellido es obligatorio.")
        return value

    def validate_telefono(self, value):
        return value.strip()

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})

        # actualizar user
        if "first_name" in user_data:
            instance.user.first_name = user_data["first_name"]

        if "last_name" in user_data:
            instance.user.last_name = user_data["last_name"]

        instance.user.save()

        # actualizar perfil web
        if "telefono" in validated_data:
            instance.telefono = validated_data["telefono"]

        instance.save()

        return instance