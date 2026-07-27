from django.core.exceptions import ValidationError

from pedidos_internos.models import PedidoDestino, PedidoInterno, PedidoMovimiento, UsuarioSector
from pedidos_internos.services import workflow_service
from pedidos_internos.tests.base import PedidosInternosBaseTestCase


class WorkflowServiceTests(PedidosInternosBaseTestCase):
    def test_marcar_leido_registra_primera_lectura_sin_duplicar(self):
        _pedido, destino = self.crear_pedido()

        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        destino.refresh_from_db()

        self.assertTrue(destino.leido)
        self.assertIsNotNone(destino.fecha_leido)
        self.assertEqual(destino.leido_por, self.miembro)
        self.assertEqual(
            destino.movimientos.filter(accion=PedidoMovimiento.Accion.LEIDO).count(),
            1,
        )

    def test_usuario_ajeno_no_puede_marcar_leido(self):
        _pedido, destino = self.crear_pedido()
        with self.assertRaises(ValidationError):
            workflow_service.marcar_leido(destino=destino, usuario=self.otro)

    def test_tomar_requiere_lectura_y_asigna_responsable(self):
        _pedido, destino = self.crear_pedido()
        with self.assertRaises(ValidationError):
            workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)

        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)
        destino.refresh_from_db()

        self.assertEqual(destino.estado, PedidoDestino.Estado.RECIBIDO)
        self.assertEqual(destino.responsable, self.miembro)
        self.assertTrue(destino.movimientos.filter(accion=PedidoMovimiento.Accion.RECIBIDO).exists())

    def test_tomar_rechaza_usuario_ajeno_y_destino_terminal(self):
        _pedido, destino = self.crear_pedido()
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        with self.assertRaises(ValidationError):
            workflow_service.tomar_pedido(destino=destino, usuario=self.otro)
        workflow_service.rechazar(destino=destino, usuario=self.miembro, motivo="No corresponde")
        with self.assertRaises(ValidationError):
            workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)

    def test_iniciar_proceso_requiere_recibido_y_registra_movimiento(self):
        _pedido, destino = self.crear_pedido()
        with self.assertRaises(ValidationError):
            workflow_service.iniciar_proceso(destino=destino, usuario=self.miembro)
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)
        workflow_service.iniciar_proceso(destino=destino, usuario=self.miembro)
        destino.refresh_from_db()
        self.assertEqual(destino.estado, PedidoDestino.Estado.EN_PROCESO)
        self.assertTrue(destino.movimientos.filter(accion=PedidoMovimiento.Accion.EN_PROCESO).exists())

    def test_comentar_no_cambia_estado_y_pedido_cancelado_lo_bloquea(self):
        pedido, destino = self.crear_pedido()
        estado = destino.estado
        workflow_service.agregar_comentario(destino=destino, usuario=self.miembro, comentario="Seguimiento")
        destino.refresh_from_db()
        self.assertEqual(destino.estado, estado)
        self.assertTrue(destino.movimientos.filter(accion=PedidoMovimiento.Accion.COMENTARIO, detalle="Seguimiento").exists())
        workflow_service.cancelar_pedido(pedido=pedido, usuario=self.solicitante, motivo="Ya no se necesita")
        with self.assertRaises(ValidationError):
            workflow_service.agregar_comentario(destino=destino, usuario=self.miembro, comentario="Tarde")

    def test_derivar_crea_nuevo_destino_y_conserva_original(self):
        pedido, destino = self.crear_pedido()
        nuevo = workflow_service.derivar(destino_origen=destino, sector_destino=self.derivacion, usuario=self.miembro, motivo="Intervención especializada")
        destino.refresh_from_db()
        self.assertEqual(destino.estado, PedidoDestino.Estado.PENDIENTE)
        self.assertEqual(pedido.destinos.count(), 2)
        self.assertEqual(nuevo.sector_destino, self.derivacion)
        self.assertTrue(nuevo.movimientos.filter(accion=PedidoMovimiento.Accion.ENVIADO).exists())
        self.assertTrue(destino.movimientos.filter(accion=PedidoMovimiento.Accion.DERIVADO, detalle="Intervención especializada").exists())

    def test_derivar_impide_duplicado_ajeno_y_terminal(self):
        _pedido, destino = self.crear_pedido()
        workflow_service.derivar(destino_origen=destino, sector_destino=self.derivacion, usuario=self.miembro)
        with self.assertRaises(ValidationError):
            workflow_service.derivar(destino_origen=destino, sector_destino=self.derivacion, usuario=self.miembro)
        with self.assertRaises(ValidationError):
            workflow_service.derivar(destino_origen=destino, sector_destino=self.origen, usuario=self.otro)
        workflow_service.rechazar(destino=destino, usuario=self.miembro, motivo="Cierre")
        with self.assertRaises(ValidationError):
            workflow_service.derivar(destino_origen=destino, sector_destino=self.origen, usuario=self.miembro)

    def test_resolver_exige_resultado_y_actualiza_estado_global(self):
        pedido, destino = self.crear_pedido()
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)
        workflow_service.iniciar_proceso(destino=destino, usuario=self.miembro)
        with self.assertRaises(ValidationError):
            workflow_service.resolver(destino=destino, usuario=self.miembro, resultado="")
        workflow_service.resolver(destino=destino, usuario=self.miembro, resultado="Completado")
        destino.refresh_from_db(); pedido.refresh_from_db()
        self.assertEqual(destino.estado, PedidoDestino.Estado.RESUELTO)
        self.assertEqual(pedido.estado, PedidoInterno.Estado.RESUELTO)
        self.assertTrue(destino.movimientos.filter(accion=PedidoMovimiento.Accion.RESUELTO, detalle="Completado").exists())

    def test_rechazar_exige_motivo_y_actualiza_estado_global(self):
        pedido, destino = self.crear_pedido()
        with self.assertRaises(ValidationError):
            workflow_service.rechazar(destino=destino, usuario=self.miembro, motivo="")
        workflow_service.rechazar(destino=destino, usuario=self.miembro, motivo="No corresponde")
        destino.refresh_from_db(); pedido.refresh_from_db()
        self.assertEqual(destino.estado, PedidoDestino.Estado.RECHAZADO)
        self.assertEqual(pedido.estado, PedidoInterno.Estado.RECHAZADO)
        self.assertTrue(destino.movimientos.filter(accion=PedidoMovimiento.Accion.RECHAZADO).exists())

    def test_cancelar_permisos_finalizacion_y_bloqueo_posterior(self):
        pedido, destino = self.crear_pedido()
        with self.assertRaises(ValidationError):
            workflow_service.cancelar_pedido(pedido=pedido, usuario=self.otro, motivo="Sin permiso")
        workflow_service.cancelar_pedido(pedido=pedido, usuario=self.solicitante, motivo="Error de carga")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoInterno.Estado.CANCELADO)
        with self.assertRaises(ValidationError):
            workflow_service.marcar_leido(destino=destino, usuario=self.miembro)

        pedido_final, destino_final = self.crear_pedido()
        workflow_service.rechazar(destino=destino_final, usuario=self.miembro, motivo="Finalizado")
        with self.assertRaises(ValidationError):
            workflow_service.cancelar_pedido(pedido=pedido_final, usuario=self.solicitante, motivo="Tarde")

    def test_staff_autorizado_puede_cancelar(self):
        pedido, _destino = self.crear_pedido()
        workflow_service.cancelar_pedido(pedido=pedido, usuario=self.staff_sin_membresia, motivo="Intervención administrativa")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoInterno.Estado.CANCELADO)

    def test_segundo_usuario_no_puede_tomar_destino_ya_recibido(self):
        _pedido, destino = self.crear_pedido()
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)

        with self.assertRaises(ValidationError):
            workflow_service.tomar_pedido(
                destino=destino,
                usuario=self.staff_miembro,
            )

        destino.refresh_from_db()
        self.assertEqual(destino.responsable, self.miembro)

    def test_estado_global_con_resuelto_y_pendiente_es_en_proceso(self):
        pedido, destino = self.crear_pedido(
            destinos=[self.destino, self.derivacion]
        )
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)
        workflow_service.iniciar_proceso(destino=destino, usuario=self.miembro)
        workflow_service.resolver(destino=destino, usuario=self.miembro, resultado="Listo")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoInterno.Estado.EN_PROCESO)

    def test_estado_global_resuelto_y_rechazado_es_parcial(self):
        pedido, destino = self.crear_pedido(
            destinos=[self.destino, self.derivacion]
        )
        UsuarioSector.objects.create(usuario=self.miembro, sector=self.derivacion)
        destino_derivado = pedido.destinos.get(sector_destino=self.derivacion)
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)
        workflow_service.iniciar_proceso(destino=destino, usuario=self.miembro)
        workflow_service.resolver(destino=destino, usuario=self.miembro, resultado="Listo")
        workflow_service.rechazar(destino=destino_derivado, usuario=self.miembro, motivo="No corresponde")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, PedidoInterno.Estado.PARCIAL)

    def test_sector_desactivado_impide_operar(self):
        _pedido, destino = self.crear_pedido()
        self.destino.activo = False
        self.destino.save(update_fields=["activo"])
        with self.assertRaises(ValidationError):
            workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
