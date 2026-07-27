from django.db import transaction

from .models import Empleado


@transaction.atomic
def asignar_rol(*, empleado, rol):
    empleado = Empleado.objects.select_for_update().get(pk=empleado.pk)
    rol_anterior = empleado.rol

    if rol_anterior_id := empleado.rol_id:
        if rol is None or rol_anterior_id != rol.pk:
            empleado.usuario.groups.remove(rol_anterior.grupo)

    if rol is not None:
        empleado.usuario.groups.add(rol.grupo)

    if empleado.rol_id != getattr(rol, "pk", None):
        empleado.rol = rol
        empleado.save(update_fields=["rol", "actualizado"])

    return empleado
