# gestion/backend/web_clientes/serializers.py
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from clientes.models import Cliente
from .models import ClienteWeb


class RegistroClienteWebSerializer(serializers.Serializer):
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

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=nombre,
            last_name=apellido,
        )

        cliente = Cliente.objects.create(
            nombre=nombre,
            apellido=apellido,
            email=email,
        )

        cliente_web = ClienteWeb.objects.create(
            user=user,
            cliente=cliente,
            telefono=telefono,
            acepta_terminos=acepta_terminos,
        )

        return cliente_web


class LoginClienteWebSerializer(serializers.Serializer):
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


class GoogleLoginClienteWebSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True)

    def validate(self, data):
        credential = data.get("credential", "").strip()

        if not credential:
            raise serializers.ValidationError("Falta credential de Google.")

        if not settings.GOOGLE_CLIENT_ID:
            raise serializers.ValidationError("GOOGLE_CLIENT_ID no configurado en backend.")

        try:
            google_data = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception:
            raise serializers.ValidationError("Token de Google inválido.")

        email = google_data.get("email", "").strip().lower()
        email_verified = google_data.get("email_verified", False)

        if not email:
            raise serializers.ValidationError("Google no devolvió email.")

        if not email_verified:
            raise serializers.ValidationError("El email de Google no está verificado.")

        data["google_data"] = google_data
        data["email"] = email
        return data

    @transaction.atomic
    def save(self):
        google_data = self.validated_data["google_data"]
        email = self.validated_data["email"]

        nombre = google_data.get("given_name", "") or ""
        apellido = google_data.get("family_name", "") or ""

        user = User.objects.filter(email__iexact=email).first()

        if not user:
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=nombre,
                last_name=apellido,
            )
            user.set_unusable_password()
            user.is_staff = False
            user.is_superuser = False
            user.save()

        if not hasattr(user, "cliente_web"):
            cliente = Cliente.objects.create(
                nombre=nombre or email,
                apellido=apellido,
                email=email,
            )

            cliente_web = ClienteWeb.objects.create(
                user=user,
                cliente=cliente,
                activo=True,
                email_verificado=True,
                acepta_terminos=True,
            )
        else:
            cliente_web = user.cliente_web

            if not cliente_web.activo:
                raise serializers.ValidationError("El usuario web está inactivo.")

            if not cliente_web.email_verificado:
                cliente_web.email_verificado = True
                cliente_web.save(update_fields=["email_verificado"])

        return user, cliente_web


class ClienteWebSerializer(serializers.ModelSerializer):
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

        nombre = user_data.get("first_name")
        apellido = user_data.get("last_name")
        telefono = validated_data.get("telefono")

        if nombre is not None:
            instance.user.first_name = nombre

        if apellido is not None:
            instance.user.last_name = apellido

        instance.user.save()

        if telefono is not None:
            instance.telefono = telefono

        instance.save()

        # Sincronizar también con el Cliente comercial vinculado
        cliente = instance.cliente

        if cliente:
            if nombre is not None:
                cliente.nombre = nombre

            if apellido is not None:
                cliente.apellido = apellido

            if telefono is not None:
                cliente.telefono = telefono

            # El email no es editable desde perfil,
            # pero lo mantenemos sincronizado desde el usuario.
            cliente.email = instance.user.email

            cliente.save()

        return instance