from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from pedidos_internos.models import UsuarioSector
from personal.access import puede_acceder_administracion
from personal.models import Empleado


class Command(BaseCommand):
    help = "Informa inconsistencias de Personal sin modificar datos."

    def handle(self, *args, **options):
        User = get_user_model()
        consultas = {
            "Staff sin Empleado": User.objects.filter(is_staff=True, empleado__isnull=True),
            "Usuarios con sector sin Empleado": User.objects.filter(
                empleado__isnull=True,
                id__in=UsuarioSector.objects.values("usuario_id"),
            ),
            "Empleados sin rol": User.objects.filter(empleado__rol__isnull=True),
        }
        administrativos_sin_sector = [
            empleado.usuario
            for empleado in Empleado.objects.select_related("usuario")
            if puede_acceder_administracion(empleado.usuario)
            and not UsuarioSector.objects.filter(
                usuario=empleado.usuario,
                activo=True,
                sector__activo=True,
            ).exists()
        ]

        for titulo, usuarios in consultas.items():
            self.stdout.write(self.style.WARNING(f"\n{titulo}:"))
            filas = list(usuarios.distinct())
            self.stdout.write("  " + (", ".join(user.get_username() for user in filas) or "ninguno"))
        self.stdout.write(self.style.WARNING("\nAdministrativos sin sector:"))
        self.stdout.write("  " + (", ".join(user.get_username() for user in administrativos_sin_sector) or "ninguno"))
