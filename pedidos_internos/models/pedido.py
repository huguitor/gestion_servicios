# backend/pedidos_internos/models/pedido.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .sector import Sector
from .usuario_sector import UsuarioSector


class PedidoInterno(models.Model):
    """
    Cabecera general de un pedido interno.

    El procesamiento operativo ocurre en PedidoDestino.
    El estado de esta cabecera representa un resumen global de todos
    los destinos y no debe modificarse directamente desde la API.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTO = "resuelto", "Resuelto"
        PARCIAL = "parcial", "Finalizado parcialmente"
        RECHAZADO = "rechazado", "Rechazado"
        CANCELADO = "cancelado", "Cancelado"

        # Estados históricos conservados temporalmente para no romper
        # pedidos existentes ni código previo del Sprint 1.
        RECIBIDO = "recibido", "Recibido"
        DERIVADO = "derivado", "Derivado"
        ENVIADO = "enviado", "Enviado"
        ENTREGADO = "entregado", "Entregado"

    class Prioridad(models.TextChoices):
        BAJA = "baja", "Baja"
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    ESTADOS_TERMINALES = {
        Estado.RESUELTO,
        Estado.PARCIAL,
        Estado.RECHAZADO,
        Estado.CANCELADO,
        Estado.ENTREGADO,  # Compatibilidad histórica
    }

    numero = models.PositiveIntegerField(
        unique=True,
        editable=False,
        null=True,
        blank=True,
    )

    fecha = models.DateField(
        default=timezone.localdate,
    )

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
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        help_text=(
            "Estado global calculado a partir de los destinos. "
            "No debe modificarse directamente."
        ),
    )

    prioridad = models.CharField(
        max_length=10,
        choices=Prioridad.choices,
        default=Prioridad.NORMAL,
    )

    observaciones = models.TextField(
        blank=True,
        default="",
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Pedido interno"
        verbose_name_plural = "Pedidos internos"
        indexes = [
            models.Index(
                fields=["estado", "prioridad"],
                name="pint_pedido_estado_prio_idx",
            ),
            models.Index(
                fields=["sector_origen", "creado"],
                name="pint_pedido_origen_fecha_idx",
            ),
            models.Index(
                fields=["solicitante", "creado"],
                name="pint_pedido_solic_fecha_idx",
            ),
        ]

    def __str__(self):
        return f"Pedido #{self.numero or self.pk}"

    @property
    def es_terminal(self):
        return self.estado in self.ESTADOS_TERMINALES

    def save(self, *args, **kwargs):
        """
        Conserva temporalmente el mecanismo actual de numeración.

        Este cálculo todavía tiene riesgo de colisión concurrente.
        Se reemplazará después de revisar pedido_service.py para no
        romper el flujo de creación existente.
        """
        if self.numero is None:
            ultimo = (
                PedidoInterno.objects
                .order_by("-numero")
                .values_list("numero", flat=True)
                .first()
            )
            self.numero = (ultimo or 0) + 1

        self.full_clean()
        super().save(*args, **kwargs)

    def registrar_movimiento(
        self,
        usuario,
        accion,
        detalle="",
        destino=None,
        estado_anterior=None,
        estado_nuevo=None,
        metadata=None,
    ):
        """
        Método de compatibilidad temporal.

        Las nuevas operaciones deben crear movimientos mediante
        WorkflowService. Se conserva porque los servicios existentes
        pueden utilizarlo actualmente.
        """
        from .movimiento import PedidoMovimiento

        return PedidoMovimiento.objects.create(
            pedido=self,
            destino=destino,
            usuario=usuario,
            accion=accion,
            detalle=detalle,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            metadata=metadata or {},
        )

    def clean(self):
        super().clean()

        if not self.solicitante_id or not self.sector_origen_id:
            return

        pertenece = UsuarioSector.objects.filter(
            usuario_id=self.solicitante_id,
            sector_id=self.sector_origen_id,
            activo=True,
        ).exists()

        if not pertenece:
            raise ValidationError({
                "sector_origen": (
                    "El usuario no pertenece activamente "
                    "al sector de origen."
                )
            })