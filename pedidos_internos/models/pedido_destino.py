# gestion/backend/pedidos_internos/models/pedido_destino.py

from django.conf import settings
from django.db import models

from .pedido import PedidoInterno
from .sector import Sector


class PedidoDestino(models.Model):
    """
    Copia lógica de un pedido dirigida a un sector destino.

    Un pedido puede enviarse a varios sectores; cada uno recibe su
    propio PedidoDestino con su estado, lectura y responsable.
    """

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("recibido", "Recibido"),
        ("en_proceso", "En proceso"),
        ("resuelto", "Resuelto"),
        ("rechazado", "Rechazado"),
    ]

    pedido = models.ForeignKey(
        PedidoInterno,
        on_delete=models.CASCADE,
        related_name="destinos",
    )

    sector_destino = models.ForeignKey(
        Sector,
        on_delete=models.PROTECT,
        related_name="pedidos_destino",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente",
    )

    leido = models.BooleanField(default=False)
    fecha_leido = models.DateTimeField(null=True, blank=True)

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destinos_responsable",
    )

    observacion = models.TextField(blank=True, default="")

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("pedido", "sector_destino")
        verbose_name = "Destino de pedido"
        verbose_name_plural = "Destinos de pedido"
        ordering = ["pedido", "sector_destino"]

    def __str__(self):
        return f"Pedido #{self.pedido_id} → {self.sector_destino.codigo}"
