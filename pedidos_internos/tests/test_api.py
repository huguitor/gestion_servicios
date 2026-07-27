from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from pedidos_internos.models import (
    PedidoDestino,
    PedidoInterno,
    PedidoInternoDetalle,
    PedidoMovimiento,
    Sector,
    UsuarioSector,
)
from productos.models import Producto, Servicio


class PedidosInternosAPITestCase(APITestCase):
    def setUp(self):
        self.license_patch = patch(
            "pedidos_internos.api.views.license_manager.is_enabled",
            return_value=True,
        )
        self.license_patch.start()
        self.addCleanup(self.license_patch.stop)

        user_model = get_user_model()
        self.usuario = user_model.objects.create_user(
            username="operador",
            password=None,
        )
        self.otro_usuario = user_model.objects.create_user(
            username="otro-operador",
            password=None,
        )
        self.sector_principal = Sector.objects.create(
            codigo="TALLER",
            nombre="Taller",
        )
        self.sector_secundario = Sector.objects.create(
            codigo="COMPRAS",
            nombre="Compras",
        )
        self.sector_inactivo = Sector.objects.create(
            codigo="BAJA",
            nombre="Sector inactivo",
            activo=False,
        )
        UsuarioSector.objects.create(
            usuario=self.usuario,
            sector=self.sector_principal,
            principal=True,
        )
        UsuarioSector.objects.create(
            usuario=self.usuario,
            sector=self.sector_secundario,
            activo=False,
        )
        UsuarioSector.objects.create(
            usuario=self.usuario,
            sector=self.sector_inactivo,
        )

    def test_mis_sectores_requiere_autenticacion(self):
        response = self.client.get(reverse("pedidos-internos-mis-sectores"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mis_sectores_excluye_inactivos_y_prioriza_principal(self):
        sector_alfabetico = Sector.objects.create(
            codigo="ALMACEN",
            nombre="Almacén",
        )
        UsuarioSector.objects.create(
            usuario=self.usuario,
            sector=sector_alfabetico,
        )
        self.client.force_authenticate(self.usuario)

        response = self.client.get(reverse("pedidos-internos-mis-sectores"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [sector["id"] for sector in response.data],
            [self.sector_principal.id, sector_alfabetico.id],
        )
        self.assertTrue(response.data[0]["principal"])

    def test_dashboard_rechaza_sector_sin_membresia_activa(self):
        self.client.force_authenticate(self.usuario)

        response = self.client.get(
            reverse("pedidos-internos-dashboard"),
            {"sector": self.sector_secundario.id},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_aísla_sector_y_usuario_y_cuenta_estados(self):
        UsuarioSector.objects.create(
            usuario=self.otro_usuario,
            sector=self.sector_secundario,
            principal=True,
        )
        pedido_propio = PedidoInterno.objects.create(
            solicitante=self.usuario,
            sector_origen=self.sector_principal,
        )
        pedido_otro = PedidoInterno.objects.create(
            solicitante=self.otro_usuario,
            sector_origen=self.sector_secundario,
        )
        PedidoDestino.objects.create(
            pedido=pedido_propio,
            sector_destino=self.sector_principal,
        )
        PedidoDestino.objects.create(
            pedido=pedido_otro,
            sector_destino=self.sector_principal,
            estado=PedidoDestino.Estado.RECHAZADO,
        )
        PedidoDestino.objects.create(
            pedido=pedido_otro,
            sector_destino=self.sector_secundario,
            estado=PedidoDestino.Estado.RESUELTO,
            fecha_estado=timezone.now(),
        )
        self.client.force_authenticate(self.usuario)

        response = self.client.get(
            reverse("pedidos-internos-dashboard"),
            {"sector": self.sector_principal.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["bandeja"]["total"], 2)
        self.assertEqual(response.data["bandeja"]["pendientes"], 1)
        self.assertEqual(response.data["bandeja"]["rechazados"], 1)
        self.assertEqual(response.data["mis_pedidos"]["total"], 1)
        self.assertEqual(response.data["mis_pedidos"]["pendientes"], 1)


class CrearPedidoInternoAPITests(APITestCase):
    def setUp(self):
        self.license_patch = patch(
            "pedidos_internos.api.views.license_manager.is_enabled",
            return_value=True,
        )
        self.license_patch.start()
        self.addCleanup(self.license_patch.stop)
        user_model = get_user_model()
        self.usuario = user_model.objects.create_user(username="creador", password=None)
        self.otro = user_model.objects.create_user(username="sin-sector", password=None)
        self.origen = Sector.objects.create(codigo="ORIGEN-API", nombre="Origen API")
        self.destino = Sector.objects.create(codigo="DESTINO-API", nombre="Destino API")
        self.destino_dos = Sector.objects.create(codigo="DESTINO2-API", nombre="Segundo destino")
        self.inactivo = Sector.objects.create(codigo="INACTIVO-API", nombre="Inactivo API", activo=False)
        UsuarioSector.objects.create(usuario=self.usuario, sector=self.origen, principal=True)
        self.producto = Producto.objects.create(nombre="Producto prueba", precio_venta="10.00")
        self.servicio = Servicio.objects.create(nombre="Servicio prueba")
        self.client.force_authenticate(self.usuario)

    def payload(self, *, destinos=None, detalles=None):
        return {
            "fecha": timezone.localdate().isoformat(),
            "sector_origen": self.origen.id,
            "prioridad": "normal",
            "observaciones": "Pedido desde prueba API",
            "destinos": destinos if destinos is not None else [self.destino.id],
            "detalles": detalles if detalles is not None else [{
                "tipo": "otro",
                "producto": None,
                "servicio": None,
                "descripcion": "Trabajo solicitado",
                "cantidad": 1,
                "observacion": "",
            }],
        }

    def crear(self, payload=None):
        return self.client.post(
            reverse("pedidos-internos-list"),
            payload or self.payload(),
            format="json",
        )

    def test_crea_pedido_un_destino_movimientos_estado_y_numero(self):
        response = self.crear()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoInterno.objects.get(pk=response.data["id"])
        self.assertEqual(pedido.estado, PedidoInterno.Estado.PENDIENTE)
        self.assertEqual(pedido.numero, 1)
        self.assertEqual(pedido.destinos.count(), 1)
        self.assertEqual(pedido.movimientos.filter(accion=PedidoMovimiento.Accion.CREADO).count(), 1)
        self.assertEqual(pedido.movimientos.filter(accion=PedidoMovimiento.Accion.ENVIADO).count(), 1)

    def test_crea_pedido_con_multiples_destinos(self):
        response = self.crear(self.payload(destinos=[self.destino.id, self.destino_dos.id]))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pedido = PedidoInterno.objects.get(pk=response.data["id"])
        self.assertSetEqual(set(pedido.destinos.values_list("sector_destino_id", flat=True)), {self.destino.id, self.destino_dos.id})
        self.assertEqual(pedido.movimientos.filter(accion=PedidoMovimiento.Accion.ENVIADO).count(), 2)

    def test_crea_detalle_producto(self):
        response = self.crear(self.payload(detalles=[{"tipo": "producto", "producto": self.producto.id, "servicio": None, "descripcion": "", "cantidad": 2, "observacion": "Cuidar embalaje"}]))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        detalle = PedidoInternoDetalle.objects.get(pedido_id=response.data["id"])
        self.assertEqual(detalle.producto, self.producto)
        self.assertEqual(detalle.cantidad, 2)

    def test_crea_detalle_servicio(self):
        response = self.crear(self.payload(detalles=[{"tipo": "servicio", "producto": None, "servicio": self.servicio.id, "descripcion": "", "cantidad": 1, "observacion": ""}]))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PedidoInternoDetalle.objects.get(pedido_id=response.data["id"]).servicio, self.servicio)

    def test_crea_detalle_otro(self):
        response = self.crear()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        detalle = PedidoInternoDetalle.objects.get(pedido_id=response.data["id"])
        self.assertEqual(detalle.tipo, PedidoInternoDetalle.TIPO_OTRO)
        self.assertEqual(detalle.descripcion, "Trabajo solicitado")

    def test_rechaza_sin_destinos_y_sin_detalles(self):
        response_destinos = self.crear(self.payload(destinos=[]))
        response_detalles = self.crear(self.payload(detalles=[]))
        self.assertEqual(response_destinos.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destinos", response_destinos.data)
        self.assertEqual(response_detalles.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detalles", response_detalles.data)

    def test_valida_cantidad_y_tipo_de_detalle(self):
        inválido = self.payload(detalles=[{"tipo": "producto", "producto": None, "servicio": None, "descripcion": "", "cantidad": 0, "observacion": ""}])
        response = self.crear(inválido)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detalles", response.data)

    def test_valida_sector_origen_autorizado(self):
        self.client.force_authenticate(self.otro)
        response = self.crear()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sector_origen", response.data)

    def test_rechaza_destino_inactivo_y_sector_origen_como_destino(self):
        response_inactivo = self.crear(self.payload(destinos=[self.inactivo.id]))
        response_origen = self.crear(self.payload(destinos=[self.origen.id]))
        self.assertEqual(response_inactivo.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destinos", response_inactivo.data)
        self.assertEqual(response_origen.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destinos", response_origen.data)

    def test_numeracion_correlativa_actual(self):
        primero = self.crear()
        segundo = self.crear()
        pedido_uno = PedidoInterno.objects.get(pk=primero.data["id"])
        pedido_dos = PedidoInterno.objects.get(pk=segundo.data["id"])
        self.assertEqual(pedido_dos.numero, pedido_uno.numero + 1)

    def test_pedido_creado_aparece_en_mis_pedidos_bandeja_dashboard_y_detalle(self):
        receptor = get_user_model().objects.create_user(
            username="receptor-api",
            password=None,
        )
        UsuarioSector.objects.create(usuario=receptor, sector=self.destino)
        creado = self.crear()
        pedido_id = creado.data["id"]

        mis_pedidos = self.client.get(reverse("pedidos-internos-mis-pedidos"))
        self.assertTrue(any(pedido["id"] == pedido_id for pedido in mis_pedidos.data))

        self.client.force_authenticate(receptor)
        bandeja = self.client.get(
            reverse("pedidos-internos-bandeja"),
            {"sector": self.destino.id},
        )
        dashboard = self.client.get(
            reverse("pedidos-internos-dashboard"),
            {"sector": self.destino.id},
        )
        detalle = self.client.get(
            reverse("pedidos-internos-detail", args=[pedido_id]),
        )

        self.assertEqual(bandeja.status_code, status.HTTP_200_OK)
        self.assertEqual(len(bandeja.data), 1)
        self.assertEqual(bandeja.data[0]["pedido"], pedido_id)
        self.assertEqual(dashboard.data["bandeja"]["total"], 1)
        self.assertEqual(detalle.status_code, status.HTTP_200_OK)
        self.assertEqual(detalle.data["id"], pedido_id)
