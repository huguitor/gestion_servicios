# gestion/backend/pedidos_internos/models/pedido_detalle.py

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .pedido import PedidoInterno


class PedidoInternoDetalle(models.Model):
    """
    Renglón de un pedido interno.

    Puede representar:

    - Un producto del catálogo.
    - Un servicio del catálogo.
    - Un pedido libre ("Otro").

    En producto y servicio la descripción puede autocompletarse desde
    el catálogo. En "Otro" la descripción es obligatoria.
    """

    TIPO_PRODUCTO = "producto"
    TIPO_SERVICIO = "servicio"
    TIPO_OTRO = "otro"

    TIPO_CHOICES = [
        (TIPO_PRODUCTO, "Producto"),
        (TIPO_SERVICIO, "Servicio"),
        (TIPO_OTRO, "Otro"),
    ]

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_PRODUCTO,
    )

    pedido = models.ForeignKey(
        PedidoInterno,
        on_delete=models.CASCADE,
        related_name="detalles",
    )

    producto = models.ForeignKey(
        "productos.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedido_interno_detalles",
    )

    servicio = models.ForeignKey(
        "productos.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedido_interno_detalles",
    )

    descripcion = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Descripción del renglón. "
            "Obligatoria para tipo 'Otro'."
        ),
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    observacion = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Aclaración adicional del renglón."
        ),
    )

    class Meta:
        verbose_name = "Detalle de pedido interno"
        verbose_name_plural = "Detalles de pedido interno"

    def __str__(self):
        return f"{self.descripcion or 'Renglón'} x {self.cantidad}"

    def clean(self):

        if self.tipo == self.TIPO_PRODUCTO:

            if not self.producto:
                raise ValidationError(
                    "Debe seleccionar un producto."
                )

            if self.servicio:
                raise ValidationError(
                    "Un renglón de tipo Producto no puede tener servicio."
                )

        elif self.tipo == self.TIPO_SERVICIO:

            if not self.servicio:
                raise ValidationError(
                    "Debe seleccionar un servicio."
                )

            if self.producto:
                raise ValidationError(
                    "Un renglón de tipo Servicio no puede tener producto."
                )

        elif self.tipo == self.TIPO_OTRO:

            if not (self.descripcion or "").strip():
                raise ValidationError(
                    "Debe indicar una descripción."
                )

            if self.producto or self.servicio:
                raise ValidationError(
                    "Un renglón de tipo Otro no puede tener producto ni servicio."
                )

        else:
            raise ValidationError(
                "Tipo de renglón inválido."
            )

    def save(self, *args, **kwargs):

        self.full_clean()

        # Producto y Servicio:
        # autocompletar descripción si viene vacía.
        if self.tipo in (
            self.TIPO_PRODUCTO,
            self.TIPO_SERVICIO,
        ):

            if not (self.descripcion or "").strip():

                if self.producto:
                    self.descripcion = self.producto.nombre

                elif self.servicio:
                    self.descripcion = self.servicio.nombre

        super().save(*args, **kwargs)