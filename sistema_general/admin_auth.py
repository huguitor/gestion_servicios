# gestion/backend/sistema_general/admin_auth.py

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


class AdminLoginView(APIView):
    """
    Login exclusivo para el panel interno de administración React.

    Seguridad:
    - No permite clientes web normales.
    - Solo permite usuarios internos con is_staff=True.
    - Usa token DRF.
    - Tiene rate limiting para reducir fuerza bruta.
    """

    permission_classes = [AllowAny]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "admin_login"

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"detail": "Usuario y contraseña son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {"detail": "Usuario inactivo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.is_staff:
            return Response(
                {"detail": "No tiene permisos para ingresar al sistema administrativo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            },
            status=status.HTTP_200_OK,
        )