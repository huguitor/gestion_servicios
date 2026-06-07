# gestion/backend/pedidos_internos/models/movimiento.py

from django.conf import settings
from django.db import models

from .pedido import PedidoInterno


class PedidoMovimiento(models.Model):
    """
    Entrada de historial / trazabilidad de un pedido interno.

    Cada acción relevante (creado, leído, derivado, etc.) queda
    registrada con su usuario y fecha.
    """

    ACCION_CHOICES = [
        ("creado", "Creado"),
        ("recibido", "Recibido"),
        ("leido", "Leído"),
        ("derivado", "Derivado"),
        ("en_proceso", "En proceso"),
        ("enviado", "Enviado"),
        ("entregado", "Entregado"),
        ("rechazado", "Rechazado"),
        ("cancelado", "Cancelado"),
        ("comentario", "Comentario"),
    ]

    pedido = models.ForeignKey(
        PedidoInterno,
        on_delete=models.CASCADE,
        related_name="movimientos",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_pedido_interno",
    )

    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    detalle = models.TextField(blank=True, default="")

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "Movimiento de pedido"
        verbose_name_plural = "Movimientos de pedido"

    def __str__(self):
        return f"Pedido #{self.pedido_id} | {self.accion}"
