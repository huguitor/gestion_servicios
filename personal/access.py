from licensing.manager import license_manager
from pedidos_internos.models import UsuarioSector


def obtener_empleado_activo(user):
    try:
        empleado = user.empleado
    except AttributeError:
        return None
    return empleado if empleado.activo else None


def puede_acceder_administracion(user):
    if not user or not user.is_active:
        return False
    try:
        empleado = user.empleado
    except AttributeError:
        # Compatibilidad temporal para staff históricos aún no regularizados.
        return bool(user.is_staff)
    return bool(
        empleado.activo
        and user.is_staff
        and user.has_perm("personal.access_admin_frontend")
    )


def puede_acceder_pedidos_internos(user):
    empleado = obtener_empleado_activo(user)
    return bool(
        user
        and user.is_active
        and empleado
        and license_manager.is_enabled("pedidos_internos")
        and UsuarioSector.objects.filter(
            usuario=user,
            activo=True,
            sector__activo=True,
        ).exists()
    )


def puede_gestionar_personal(user):
    return bool(
        puede_acceder_administracion(user)
        and user.has_perms([
            "personal.view_empleado",
            "personal.add_empleado",
            "personal.change_empleado",
            "personal.view_rolpersonal",
            "personal.add_rolpersonal",
            "personal.change_rolpersonal",
            "personal.view_cargo",
            "personal.add_cargo",
            "personal.change_cargo",
        ])
    )
