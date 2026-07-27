from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from pedidos_internos.models import PedidoMovimiento, PedidoReglaSLA
from pedidos_internos.services import workflow_service
from pedidos_internos.services.sla_service import (
    evaluar_transicion,
    obtener_sla_actual,
)
from pedidos_internos.tests.base import PedidosInternosBaseTestCase


class SLAServiceTests(PedidosInternosBaseTestCase):
    def crear_regla(self, origen="enviado", destino="leido", horas="2.00"):
        return PedidoReglaSLA.objects.create(
            sector=self.destino,
            hito_origen=origen,
            hito_destino=destino,
            horas_limite=Decimal(horas),
        )

    def test_estado_actual_sin_regla(self):
        _pedido, destino = self.crear_pedido()
        sla = obtener_sla_actual(destino=destino)
        self.assertFalse(sla["aplica"])
        self.assertEqual(sla["estado"], "sin_regla")

    def test_estado_actual_aplica_y_usa_timezone(self):
        self.crear_regla(horas="4.00")
        _pedido, destino = self.crear_pedido()
        ahora = timezone.now()
        destino.creado = ahora - timedelta(hours=1)
        destino.save(update_fields=["creado"])
        movimiento = destino.movimientos.get(accion=PedidoMovimiento.Accion.ENVIADO)
        PedidoMovimiento.objects.filter(pk=movimiento.pk).update(fecha=ahora - timedelta(hours=1))
        sla = obtener_sla_actual(destino=destino, ahora=ahora)
        self.assertTrue(timezone.is_aware(sla["fecha_limite"]))
        self.assertEqual(sla["estado"], "en_tiempo")

    def test_evaluar_transicion_dentro_y_fuera_del_plazo(self):
        self.crear_regla(horas="2.00")
        _pedido, destino = self.crear_pedido()
        inicio = timezone.now()
        dentro = evaluar_transicion(destino=destino, hito_origen="enviado", hito_destino="leido", fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=1))
        vencido = evaluar_transicion(destino=destino, hito_origen="enviado", hito_destino="leido", fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=3))
        self.assertFalse(dentro["vencido"])
        self.assertTrue(vencido["vencido"])

    def test_marcar_leido_guarda_resultado_sla_en_movimiento(self):
        self.crear_regla(horas="2.00")
        _pedido, destino = self.crear_pedido()
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        movimiento = destino.movimientos.get(accion=PedidoMovimiento.Accion.LEIDO)
        self.assertTrue(movimiento.sla_aplica)
        self.assertEqual(movimiento.sla_limite_horas, Decimal("2.00"))
        self.assertIsNotNone(movimiento.sla_duracion_horas)
        self.assertFalse(movimiento.sla_vencido)
        self.assertEqual(movimiento.metadata["sla"]["hito_destino"], "leido")

    def test_iniciar_y_resolver_guardan_sla_en_movimiento_correcto(self):
        self.crear_regla(origen="recibido", destino="en_proceso", horas="2.00")
        PedidoReglaSLA.objects.create(sector=self.destino, hito_origen="en_proceso", hito_destino="resuelto", horas_limite=Decimal("2.00"))
        _pedido, destino = self.crear_pedido()
        workflow_service.marcar_leido(destino=destino, usuario=self.miembro)
        workflow_service.tomar_pedido(destino=destino, usuario=self.miembro)
        workflow_service.iniciar_proceso(destino=destino, usuario=self.miembro)
        workflow_service.resolver(destino=destino, usuario=self.miembro, resultado="Terminado")
        en_proceso = destino.movimientos.get(accion=PedidoMovimiento.Accion.EN_PROCESO)
        resuelto = destino.movimientos.get(accion=PedidoMovimiento.Accion.RESUELTO)
        self.assertTrue(en_proceso.sla_aplica)
        self.assertTrue(resuelto.sla_aplica)
        self.assertEqual(en_proceso.metadata["sla"]["hito_origen"], "recibido")
        self.assertEqual(resuelto.metadata["sla"]["hito_destino"], "resuelto")

    def test_estado_actual_proximo_a_vencer(self):
        self.crear_regla(horas="4.00")
        _pedido, destino = self.crear_pedido()
        ahora = timezone.now()
        movimiento = destino.movimientos.get(
            accion=PedidoMovimiento.Accion.ENVIADO
        )
        PedidoMovimiento.objects.filter(pk=movimiento.pk).update(
            fecha=ahora - timedelta(hours=3, minutes=30)
        )
        sla = obtener_sla_actual(destino=destino, ahora=ahora)
        self.assertEqual(sla["estado"], "proximo_vencer")
