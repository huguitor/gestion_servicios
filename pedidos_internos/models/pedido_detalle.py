# gestion/backend/pedidos_internos/models/pedido_detalle.py

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .pedido import PedidoInterno


class PedidoInternoDetalle(models.Model):
    """
    Renglón de un pedido interno.

    Puede apuntar a un Producto del catálogo, a un Servicio (la app
    `productos` maneja ambos), o quedar como texto libre para pedidos
    no catalogados (ej. "reemplazo de lámpara"). `descripcion` siempre
    queda poblada como etiqueta legible del renglón.
    """

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
        help_text="Texto libre del pedido (o etiqueta del producto/servicio)."
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    observacion = models.TextField(
        blank=True,
        default="",
        help_text="Aclaración del renglón, ej. 'SKF preferentemente'."
    )

    class Meta:
        verbose_name = "Detalle de pedido interno"
        verbose_name_plural = "Detalles de pedido interno"

    def __str__(self):
        return f"{self.descripcion or 'Renglón'} x {self.cantidad}"

    def clean(self):
        if self.producto and self.servicio:
            raise ValidationError(
                "Un renglón no puede tener producto y servicio a la vez."
            )

        if not self.producto and not self.servicio and not (self.descripcion or "").strip():
            raise ValidationError(
                "El renglón debe tener un producto, un servicio o una descripción."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        # Autocompletar descripción legible desde el catálogo si está vacía.
        if not (self.descripcion or "").strip():
            if self.producto:
                self.descripcion = self.producto.nombre
            elif self.servicio:
                self.descripcion = self.servicio.nombre

        super().save(*args, **kwargs)
