# gestion/backend/sistema_general/admin_auth.py

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from personal.access import (
    puede_acceder_administracion,
    puede_acceder_pedidos_internos,
    puede_gestionar_personal,
)


class AdminLoginView(APIView):
    """
    Login exclusivo para el panel interno de administración React.

    Seguridad:
    - No permite clientes web normales.
    - Acepta usuarios activos y devuelve capacidades de portal.
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

        token, _ = Token.objects.get_or_create(user=user)

        try:
            empleado_activo = user.empleado.activo
        except AttributeError:
            empleado_activo = False

        acceso_admin = puede_acceder_administracion(user)
        acceso_operativo = puede_acceder_pedidos_internos(user)
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "empleado_activo": empleado_activo,
            "puede_acceder_administracion": acceso_admin,
            "puede_acceder_pedidos_internos": acceso_operativo,
            "puede_gestionar_personal": puede_gestionar_personal(user),
        }

        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )
