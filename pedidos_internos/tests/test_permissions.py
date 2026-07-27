from pedidos_internos.models import UsuarioSector
from pedidos_internos.services import workflow_permissions
from pedidos_internos.tests.base import PedidosInternosBaseTestCase


class WorkflowPermissionsTests(PedidosInternosBaseTestCase):
    def test_solicitante_no_opera_destino_si_no_es_miembro(self):
        _pedido, destino = self.crear_pedido()
        self.assertEqual(
            workflow_permissions.acciones_permitidas(self.solicitante, destino),
            [],
        )

    def test_miembro_activo_recibe_acciones_y_miembro_inactivo_no(self):
        _pedido, destino = self.crear_pedido()
        self.assertIn(
            "marcar_leido",
            workflow_permissions.acciones_permitidas(self.miembro, destino),
        )
        membresia = UsuarioSector.objects.get(usuario=self.miembro, sector=self.destino)
        membresia.activo = False
        membresia.save(update_fields=["activo"])
        self.assertEqual(
            workflow_permissions.acciones_permitidas(self.miembro, destino),
            [],
        )

    def test_staff_necesita_membresia_para_operar(self):
        _pedido, destino = self.crear_pedido()
        self.assertIn(
            "marcar_leido",
            workflow_permissions.acciones_permitidas(self.staff_miembro, destino),
        )
        self.assertEqual(
            workflow_permissions.acciones_permitidas(self.staff_sin_membresia, destino),
            [],
        )

    def test_superusuario_sin_membresia_no_opera_pero_puede_cancelar(self):
        pedido, destino = self.crear_pedido()
        self.assertEqual(
            workflow_permissions.acciones_permitidas(self.superusuario, destino),
            [],
        )
        self.assertTrue(workflow_permissions.puede_cancelar(self.superusuario, pedido))

    def test_solicitante_y_staff_pueden_cancelar_usuario_ajeno_no(self):
        pedido, _destino = self.crear_pedido()
        self.assertTrue(workflow_permissions.puede_cancelar(self.solicitante, pedido))
        self.assertTrue(workflow_permissions.puede_cancelar(self.staff_sin_membresia, pedido))
        self.assertFalse(workflow_permissions.puede_cancelar(self.otro, pedido))
