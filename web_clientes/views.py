# gestion_servicios/web_clientes/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token

from .serializers import (
    RegistroClienteWebSerializer,
    LoginClienteWebSerializer,
    ClienteWebSerializer,
    ActualizarClienteWebSerializer,
)


class RegistroClienteWebView(APIView):
    """
    Registro de cliente web.
    Usa un serializer de entrada para crear
    y otro serializer de salida para responder.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroClienteWebSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cliente_web = serializer.save()

        output_serializer = ClienteWebSerializer(cliente_web)

        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class LoginClienteWebView(APIView):
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

        serializer = ActualizarClienteWebSerializer(cliente_web, data=request.data)
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