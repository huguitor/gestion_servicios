from rest_framework.permissions import BasePermission

from .access import puede_acceder_administracion


class PuedeGestionarPersonal(BasePermission):
    """Compatibilidad: exige staff mientras las APIs generales usan IsAdminUser."""

    def has_permission(self, request, view):
        if not puede_acceder_administracion(request.user):
            return False
        required_permission = getattr(view, "required_permission", None)
        if required_permission:
            return request.user.has_perm(required_permission)
        action = getattr(view, "action", None)
        model = view.queryset.model
        operation = {
            "list": "view",
            "retrieve": "view",
            "create": "add",
            "update": "change",
            "partial_update": "change",
            "destroy": "delete",
        }.get(action, "view")
        return request.user.has_perm(f"personal.{operation}_{model._meta.model_name}")
