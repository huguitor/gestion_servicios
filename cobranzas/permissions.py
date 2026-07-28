from rest_framework.permissions import BasePermission

from personal.access import puede_acceder_administracion


class PuedeGestionarCobranzas(BasePermission):
    """Exige acceso administrativo y el permiso correspondiente a cada acción."""

    permisos_por_accion = {
        "list": "cobranzas.view_facturacobranza",
        "retrieve": "cobranzas.view_facturacobranza",
        "create": "cobranzas.add_facturacobranza",
        "update": "cobranzas.change_facturacobranza",
        "partial_update": "cobranzas.change_facturacobranza",
        # DELETE no está habilitado; permitir llegar al dispatcher produce 405.
        "destroy": "cobranzas.view_facturacobranza",
        "dashboard": "cobranzas.view_facturacobranza",
        "exportar_excel": "cobranzas.view_facturacobranza",
    }

    def has_permission(self, request, view):
        if not puede_acceder_administracion(request.user):
            return False

        action = getattr(view, "action", None)
        if action == "cobros":
            permiso = (
                "cobranzas.registrar_cobro"
                if request.method == "POST"
                else "cobranzas.view_cobro"
            )
        elif action == "seguimientos":
            permiso = (
                "cobranzas.agregar_seguimiento"
                if request.method == "POST"
                else "cobranzas.view_seguimientocobranza"
            )
        else:
            permiso = self.permisos_por_accion.get(action)

        return bool(permiso and request.user.has_perm(permiso))
