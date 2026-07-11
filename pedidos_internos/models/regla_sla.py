# backend/pedidos_internos/models/regla_sla.py

from django.core.exceptions import ValidationError
from django.db import models

from .sector import Sector


TRANSICIONES_SLA_SOPORTADAS = frozenset({
    ("enviado", "leido"),
    ("leido", "recibido"),
    ("recibido", "en_proceso"),
    ("en_proceso", "resuelto"),
})


class PedidoReglaSLA(models.Model):
    """
    Regla configurable de tiempo máximo entre dos hitos
    del workflow de un PedidoDestino.

    Ejemplos:

    - enviado -> leido
    - leido -> recibido
    - recibido -> en_proceso
    - en_proceso -> resuelto

    La regla se aplica por sector destino.
    """

    class Hito(models.TextChoices):
        ENVIADO = "enviado", "Enviado"
        LEIDO = "leido", "Leído"
        RECIBIDO = "recibido", "Recibido"
        EN_PROCESO = "en_proceso", "En proceso"
        RESUELTO = "resuelto", "Resuelto"
        RECHAZADO = "rechazado", "Rechazado"
        CANCELADO = "cancelado", "Cancelado"

    sector = models.ForeignKey(
        Sector,
        on_delete=models.PROTECT,
        db_index=False,
        related_name="reglas_sla_pedidos_internos",
    )

    hito_origen = models.CharField(
        max_length=20,
        choices=Hito.choices,
    )

    hito_destino = models.CharField(
        max_length=20,
        choices=Hito.choices,
    )

    horas_limite = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=(
            "Cantidad máxima de horas corridas permitidas "
            "para completar la transición."
        ),
    )

    activo = models.BooleanField(
        default=True,
    )

    creado = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Regla SLA de pedido interno"
        verbose_name_plural = "Reglas SLA de pedidos internos"

        ordering = [
            "sector__codigo",
            "hito_origen",
            "hito_destino",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "sector",
                    "hito_origen",
                    "hito_destino",
                ],
                name="unique_regla_sla_sector_transicion",
            ),
            models.CheckConstraint(
                condition=models.Q(horas_limite__gt=0),
                name="regla_sla_horas_limite_mayor_cero",
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    hito_origen=models.F("hito_destino")
                ),
                name="regla_sla_hitos_distintos",
            ),
        ]

    def __str__(self):
        return (
            f"{self.sector.codigo}: "
            f"{self.get_hito_origen_display()} → "
            f"{self.get_hito_destino_display()} "
            f"({self.horas_limite} h)"
        )

    def clean(self):
        """
        Valida reglas de negocio antes de guardar.

        La base de datos también protege varias de estas condiciones,
        pero clean() devuelve errores más claros en Admin y serializers.
        """
        super().clean()

        if not self.sector_id:
            return

        if not self.sector.activo:
            raise ValidationError({
                "sector": (
                    "No se puede configurar una regla SLA "
                    "para un sector inactivo."
                )
            })

        if self.hito_origen == self.hito_destino:
            raise ValidationError({
                "hito_destino": (
                    "El hito de destino debe ser diferente "
                    "del hito de origen."
                )
            })

        if self.horas_limite is not None and self.horas_limite <= 0:
            raise ValidationError({
                "horas_limite": (
                    "La cantidad de horas debe ser mayor que cero."
                )
            })

        transicion = (
            self.hito_origen,
            self.hito_destino,
        )

        if transicion not in TRANSICIONES_SLA_SOPORTADAS:
            raise ValidationError({
                "hito_destino": (
                    "La transición SLA seleccionada todavía "
                    "no está soportada por el motor."
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
