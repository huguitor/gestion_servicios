# gestion/backend/pedidos_internos/models/pedido_destino.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .pedido import PedidoInterno
from .sector import Sector


class PedidoDestino(models.Model):
    """
    Representa el trabajo operativo de un sector sobre un pedido interno.

    El pedido pertenece operativamente al sector destino.
    El responsable es solamente el referente principal y no bloquea
    la intervención del resto de los integrantes del sector.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        RECIBIDO = "recibido", "Recibido"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTO = "resuelto", "Resuelto"
        RECHAZADO = "rechazado", "Rechazado"

    ESTADOS_TERMINALES = {
        Estado.RESUELTO,
        Estado.RECHAZADO,
    }

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
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    fecha_estado = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha desde la cual el destino se encuentra en el estado actual.",
    )

    leido = models.BooleanField(
        default=False,
        help_text="Indica si algún usuario del sector abrió el detalle.",
    )

    fecha_leido = models.DateTimeField(
        null=True,
        blank=True,
    )

    leido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destinos_leidos_primero",
        help_text="Usuario que abrió por primera vez el destino.",
    )

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destinos_responsable",
        help_text=(
            "Referente principal del sector. No bloquea la intervención "
            "de otros miembros activos del mismo sector."
        ),
    )

    observacion = models.TextField(
        blank=True,
        default="",
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Destino de pedido"
        verbose_name_plural = "Destinos de pedido"
        ordering = ["-creado"]

        constraints = [
            models.UniqueConstraint(
                fields=["pedido", "sector_destino"],
                name="unique_pedido_sector_destino",
            ),
        ]

        indexes = [
            models.Index(
                fields=["sector_destino", "estado"],
                name="pint_dest_sector_estado_idx",
            ),
            models.Index(
                fields=["sector_destino", "leido"],
                name="pint_dest_sector_leido_idx",
            ),
            models.Index(
                fields=["responsable", "estado"],
                name="pint_dest_resp_estado_idx",
            ),
        ]

    def __str__(self):
        numero = self.pedido.numero or self.pedido_id
        return f"Pedido #{numero} → {self.sector_destino.codigo}"

    @property
    def es_terminal(self):
        return self.estado in self.ESTADOS_TERMINALES

    @property
    def tiene_responsable(self):
        return self.responsable_id is not None

    def clean(self):
        """
        Protege invariantes básicas del modelo.

        Las reglas de permisos y transición pertenecen al WorkflowService.
        """
        super().clean()

        if self.leido:
            if self.fecha_leido is None:
                raise ValidationError({
                    "fecha_leido": (
                        "Un destino marcado como leído debe tener fecha de lectura."
                    )
                })

            if self.leido_por_id is None:
                raise ValidationError({
                    "leido_por": (
                        "Un destino marcado como leído debe indicar "
                        "quién realizó la primera lectura."
                    )
                })

        if not self.leido:
            if self.fecha_leido is not None or self.leido_por_id is not None:
                raise ValidationError({
                    "leido": (
                        "Un destino no leído no puede tener fecha "
                        "ni usuario de lectura."
                    )
                })

        usuarios_a_validar = {
            usuario_id
            for usuario_id in (
                self.leido_por_id,
                self.responsable_id,
            )
            if usuario_id is not None
        }
        miembros_activos = set()

        if usuarios_a_validar and self.sector_destino_id:
            from .usuario_sector import UsuarioSector

            miembros_activos = set(
                UsuarioSector.objects.filter(
                    usuario_id__in=usuarios_a_validar,
                    sector_id=self.sector_destino_id,
                    activo=True,
                    sector__activo=True,
                ).values_list("usuario_id", flat=True)
            )

        if (
            self.leido_por_id
            and self.sector_destino_id
            and self.leido_por_id not in miembros_activos
        ):
            raise ValidationError({
                "leido_por": (
                    "El usuario de la primera lectura debe pertenecer "
                    "activamente al sector destino."
                )
            })

        if (
            self.responsable_id
            and self.sector_destino_id
            and self.responsable_id not in miembros_activos
        ):
            raise ValidationError({
                "responsable": (
                    "El responsable debe pertenecer activamente "
                    "al sector destino."
                )
            })

        if self.estado in {
            self.Estado.RECIBIDO,
            self.Estado.EN_PROCESO,
            self.Estado.RESUELTO,
        } and not self.responsable_id:
            raise ValidationError({
                "responsable": (
                    "Los destinos recibidos, en proceso o resueltos "
                    "deben tener un responsable principal."
                )
            })
