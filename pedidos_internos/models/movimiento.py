# gestion/backend/pedidos_internos/models/movimiento.py

from django.conf import settings
from django.db import models


class PedidoMovimiento(models.Model):
    """
    Registro histórico e inmutable de las acciones realizadas
    sobre un pedido interno y, cuando corresponde, sobre uno
    de sus destinos.

    PedidoMovimiento no controla el flujo. Solo registra lo que
    fue validado y ejecutado por WorkflowService.
    """

    class Accion(models.TextChoices):
        CREADO = "creado", "Creado"
        ENVIADO = "enviado", "Enviado"
        LEIDO = "leido", "Leído"
        RECIBIDO = "recibido", "Recibido"
        RESPONSABLE_ASIGNADO = (
            "responsable_asignado",
            "Responsable asignado",
        )
        EN_PROCESO = "en_proceso", "En proceso"
        COMENTARIO = "comentario", "Comentario"
        DERIVADO = "derivado", "Derivado"
        RESUELTO = "resuelto", "Resuelto"
        RECHAZADO = "rechazado", "Rechazado"
        CANCELADO = "cancelado", "Cancelado"

        # Se conserva temporalmente por compatibilidad histórica.
        ENTREGADO = "entregado", "Entregado"

    pedido = models.ForeignKey(
        "pedidos_internos.PedidoInterno",
        on_delete=models.CASCADE,
        related_name="movimientos",
    )

    destino = models.ForeignKey(
        "pedidos_internos.PedidoDestino",
        on_delete=models.SET_NULL,
        db_index=False,
        null=True,
        blank=True,
        related_name="movimientos",
        help_text=(
            "Destino afectado por la acción. Puede quedar vacío "
            "en movimientos generales del pedido."
        ),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_pedido_interno",
    )

    accion = models.CharField(
        max_length=30,
        choices=Accion.choices,
    )

    estado_anterior = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    estado_nuevo = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    detalle = models.TextField(
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Información complementaria estructurada, como sectores "
            "de una derivación u otros datos de auditoría."
        ),
    )

    # Resultado histórico del SLA de la etapa que terminó.
    sla_aplica = models.BooleanField(default=False)

    sla_limite_horas = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    sla_duracion_horas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    sla_vencido = models.BooleanField(
        null=True,
        blank=True,
        help_text=(
            "Null significa que el movimiento no fue evaluado "
            "o que no tenía una regla SLA aplicable."
        ),
    )

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "Movimiento de pedido interno"
        verbose_name_plural = "Movimientos de pedidos internos"
        indexes = [
            models.Index(
                fields=["pedido", "fecha"],
                name="pint_mov_pedido_fecha_idx",
            ),
            models.Index(
                fields=["destino", "fecha"],
                name="pint_mov_destino_fecha_idx",
            ),
            models.Index(
                fields=["accion", "fecha"],
                name="pint_mov_accion_fecha_idx",
            ),
        ]

    def __str__(self):
        destino = (
            f" | destino {self.destino_id}"
            if self.destino_id
            else ""
        )
        return (
            f"Pedido #{self.pedido_id}{destino} | "
            f"{self.get_accion_display()}"
        )
