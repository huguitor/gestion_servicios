# gestion/backend/pedidos_internos/models/pedido.py

from django.conf import settings
from django.db import models
from django.utils import timezone

from .sector import Sector


class PedidoInterno(models.Model):
    """
    Cabecera de un pedido interno: un sector solicita productos y/o
    servicios y el pedido viaja entre sectores hasta resolverse.
    """

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("recibido", "Recibido"),
        ("en_proceso", "En proceso"),
        ("derivado", "Derivado"),
        ("enviado", "Enviado"),
        ("entregado", "Entregado"),
        ("rechazado", "Rechazado"),
        ("cancelado", "Cancelado"),
    ]

    PRIORIDAD_CHOICES = [
        ("baja", "Baja"),
        ("normal", "Normal"),
        ("alta", "Alta"),
        ("urgente", "Urgente"),
    ]

    numero = models.PositiveIntegerField(
        unique=True,
        editable=False,
        null=True,
        blank=True,
        help_text="Número correlativo legible (se asigna automáticamente)."
    )

    fecha = models.DateField(default=timezone.localdate)

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos_internos",
    )

    sector_origen = models.ForeignKey(
        Sector,
        on_delete=models.PROTECT,
        related_name="pedidos_origen",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente",
    )

    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default="normal",
    )

    observaciones = models.TextField(blank=True, default="")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Pedido interno"
        verbose_name_plural = "Pedidos internos"

    def __str__(self):
        return f"Pedido interno #{self.numero or self.pk}"

    def save(self, *args, **kwargs):
        if self.numero is None:
            ultimo = (
                PedidoInterno.objects
                .order_by("-numero")
                .values_list("numero", flat=True)
                .first()
            )
            self.numero = (ultimo or 0) + 1

        super().save(*args, **kwargs)

    def registrar_movimiento(self, usuario, accion, detalle=""):
        """
        Atajo para anotar una entrada en el historial del pedido.
        Importación local para evitar import circular entre modelos.
        """
        from .movimiento import PedidoMovimiento

        return PedidoMovimiento.objects.create(
            pedido=self,
            usuario=usuario,
            accion=accion,
            detalle=detalle,
        )
