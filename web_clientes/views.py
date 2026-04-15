# gestion_servicios/web_clientes/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token

from .models import ClienteWeb
from .serializers import (
    RegistroClienteWebSerializer,
    LoginClienteWebSerializer,
    ClienteWebSerializer
)


class RegistroClienteWebView(generics.CreateAPIView):
    serializer_class = RegistroClienteWebSerializer
    permission_classes = [AllowAny]


class LoginClienteWebView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginClienteWebSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user_id": user.id,
            "email": user.email,
        })


class MiPerfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cliente_web = request.user.cliente_web
        serializer = ClienteWebSerializer(cliente_web)
        return Response(serializer.data)