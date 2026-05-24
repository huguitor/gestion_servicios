# gestion/backend/web_clientes/views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import redirect
from .models import ClienteWeb
from .services import EMAIL_VERIFICATION_SALT, enviar_email_verificacion

from .serializers import (
    RegistroClienteWebSerializer,
    LoginClienteWebSerializer,
    GoogleLoginClienteWebSerializer,
    ClienteWebSerializer,
    ActualizarClienteWebSerializer,
)


class RegistroClienteWebView(APIView):
    """
    Registro de cliente web.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroClienteWebSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cliente_web = serializer.save()

        next_url = request.data.get("next", "/")

        if not isinstance(next_url, str) or not next_url.startswith("/"):
            next_url = "/"

        enviar_email_verificacion(cliente_web, next_url=next_url)

        output_serializer = ClienteWebSerializer(cliente_web)

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )


class LoginClienteWebView(APIView):
    """
    Login clásico email + password.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginClienteWebSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        cliente_web = serializer.validated_data["cliente_web"]

        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user_id": user.id,
            "email": user.email,
            "nombre": user.first_name,
            "apellido": user.last_name,
            "cliente_web_id": cliente_web.id,
        }, status=status.HTTP_200_OK)


class GoogleLoginClienteWebView(APIView):
    """
    Login / registro mediante Google OAuth.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleLoginClienteWebSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, cliente_web = serializer.save()

        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user_id": user.id,
            "email": user.email,
            "nombre": user.first_name,
            "apellido": user.last_name,
            "cliente_web_id": cliente_web.id,
        }, status=status.HTTP_200_OK)


class MiPerfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get_cliente_web(self, request):
        if not hasattr(request.user, "cliente_web"):
            return None

        return request.user.cliente_web

    def get(self, request):
        cliente_web = self.get_cliente_web(request)

        if not cliente_web:
            return Response(
                {"detail": "El usuario autenticado no tiene perfil web."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ClienteWebSerializer(cliente_web)

        return Response(serializer.data)

    def put(self, request):
        cliente_web = self.get_cliente_web(request)

        if not cliente_web:
            return Response(
                {"detail": "El usuario autenticado no tiene perfil web."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ActualizarClienteWebSerializer(
            cliente_web,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            ClienteWebSerializer(cliente_web).data,
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        cliente_web = self.get_cliente_web(request)

        if not cliente_web:
            return Response(
                {"detail": "El usuario autenticado no tiene perfil web."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ActualizarClienteWebSerializer(
            cliente_web,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            ClienteWebSerializer(cliente_web).data,
            status=status.HTTP_200_OK
        )

class VerificarEmailClienteWebView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        next_url = request.GET.get("next", "/")

        if not next_url.startswith("/"):
            next_url = "/"

        signer = TimestampSigner(salt=EMAIL_VERIFICATION_SALT)

        try:
            cliente_web_id = signer.unsign(
                token,
                max_age=60 * 60 * 24
            )
        except SignatureExpired:
            return redirect(
                f"{settings.FRONTEND_BASE_URL}/login?error=token_expirado"
            )
        except BadSignature:
            return redirect(
                f"{settings.FRONTEND_BASE_URL}/login?error=token_invalido"
            )

        try:
            cliente_web = ClienteWeb.objects.get(id=cliente_web_id)
        except ClienteWeb.DoesNotExist:
            return redirect(
                f"{settings.FRONTEND_BASE_URL}/login?error=cliente_no_existe"
            )

        if not cliente_web.email_verificado:
            cliente_web.email_verificado = True
            cliente_web.save(update_fields=["email_verificado"])

        return redirect(
            f"{settings.FRONTEND_BASE_URL}/login?verified=1"
        )

class ReenviarVerificacionEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not hasattr(request.user, "cliente_web"):
            return Response(
                {"detail": "El usuario autenticado no tiene perfil web."},
                status=status.HTTP_404_NOT_FOUND
            )

        cliente_web = request.user.cliente_web

        if cliente_web.email_verificado:
            return Response(
                {"detail": "El correo ya está verificado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        next_url = request.data.get("next", "/")

        if not isinstance(next_url, str) or not next_url.startswith("/"):
            next_url = "/"

        enviar_email_verificacion(cliente_web, next_url=next_url)

        return Response(
            {"detail": "Te enviamos un nuevo correo de verificación."},
            status=status.HTTP_200_OK
        )