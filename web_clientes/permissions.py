# gestion/backend/web_clientes/permissions.py

from rest_framework.permissions import BasePermission


class IsVerifiedClienteWeb(BasePermission):
    """
    Cliente autenticado + perfil web activo + email verificado.
    """

    message = (
        "Debe verificar su correo para acceder a esta función."
    )

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not hasattr(user, "cliente_web"):
            return False

        cliente = user.cliente_web

        return (
            cliente.activo
            and cliente.email_verificado
        )