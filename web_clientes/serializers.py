# gestion_servicios/web_clientes/serializers.py
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers

from clientes.models import Cliente
from .models import ClienteWeb


class RegistroClienteWebSerializer(serializers.Serializer):
    """
    Registro de cliente web.
    """

    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    acepta_terminos = serializers.BooleanField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        return value

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

        # Crear cliente comercial (opcional pero recomendado)
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
    Login de cliente web.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError("Credenciales inválidas.")

        if not hasattr(user, "cliente_web"):
            raise serializers.ValidationError("Usuario no tiene perfil web.")

        data["user"] = user
        data["cliente_web"] = user.cliente_web

        return data


class ClienteWebSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="user.first_name")
    apellido = serializers.CharField(source="user.last_name")
    email = serializers.EmailField(source="user.email")

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
            "fecha_alta",
        ]