from django.contrib.auth import get_user_model
from django.test import TestCase

from pedidos_internos.models import Sector, UsuarioSector
from pedidos_internos.services import pedido_service


class PedidosInternosBaseTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.solicitante = user_model.objects.create_user(
            username="solicitante",
            password=None,
        )
        self.miembro = user_model.objects.create_user(
            username="miembro",
            password=None,
        )
        self.otro = user_model.objects.create_user(
            username="ajeno",
            password=None,
        )
        self.staff_miembro = user_model.objects.create_user(
            username="staff-miembro",
            password=None,
            is_staff=True,
        )
        self.staff_sin_membresia = user_model.objects.create_user(
            username="staff-ajeno",
            password=None,
            is_staff=True,
        )
        self.superusuario = user_model.objects.create_superuser(
            username="superusuario",
            password=None,
            email="super@example.com",
        )
        self.origen = Sector.objects.create(codigo="ORIGEN", nombre="Origen")
        self.destino = Sector.objects.create(codigo="DESTINO", nombre="Destino")
        self.derivacion = Sector.objects.create(codigo="DERIVA", nombre="Derivación")
        UsuarioSector.objects.create(usuario=self.solicitante, sector=self.origen, principal=True)
        UsuarioSector.objects.create(usuario=self.miembro, sector=self.destino)
        UsuarioSector.objects.create(usuario=self.staff_miembro, sector=self.destino)

    def crear_pedido(self, *, destinos=None):
        pedido = pedido_service.crear_pedido(
            solicitante=self.solicitante,
            sector_origen=self.origen,
            detalles=[{
                "tipo": "otro",
                "descripcion": "Trabajo de prueba",
                "cantidad": 1,
            }],
            destinos=destinos or [self.destino],
        )
        return pedido, pedido.destinos.get(sector_destino=self.destino)
