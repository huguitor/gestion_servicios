# gestion_servicios/pedidos/models.py
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Pedido(models.Model):
    """
    Pedido generado desde la web.
    NO reemplaza presupuestos.
    NO usa numeración fiscal.
    NO depende de comprobantes.
    """

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("revisado", "Revisado"),
        ("contactado", "Contactado"),
        ("confirmado", "Confirmado"),
        ("entregado", "Entregado"),
        ("cancelado", "Cancelado"),
    ]
    
    cliente_web = models.ForeignKey(
        "web_clientes.ClienteWeb",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
        help_text="Cliente autenticado de la web."
    )

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos_web",
        help_text="Cliente comercial asociado, si existe."
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente"
    )

    observaciones_cliente = models.TextField(
        blank=True,
        default="",
        help_text="Observaciones escritas por el cliente desde la web."
    )

    observaciones_internas = models.TextField(
        blank=True,
        default="",
        help_text="Notas internas del equipo."
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["creado"]),
        ]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        cliente_str = str(self.cliente) if self.cliente else "Cliente web sin vincular"
        return f"Pedido #{self.id} - {cliente_str} - {self.estado}"

    def recalcular_totales(self):
        """
        Recalcula subtotal y total a partir de los ítems del pedido.
        Por ahora total = subtotal.
        Más adelante, si querés sumar recargos, descuentos o envío,
        este método es el lugar correcto.
        """
        subtotal = sum(
            (item.subtotal for item in self.items.all()),
            Decimal("0.00")
        )

        self.subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.total = self.subtotal

    def save(self, *args, **kwargs):
        """
        Guardado normal del pedido.
        No recalcula antes del primer save porque puede no tener items aún.
        """
        super().save(*args, **kwargs)


class PedidoItem(models.Model):
    """
    Ítem de pedido.
    Puede referenciar:
    - un producto (mercadería)
    - un servicio

    Guarda snapshot para no depender de cambios futuros
    en nombre, código o precio.
    """

    TIPO_ITEM_CHOICES = [
        ("mercaderia", "Mercadería"),
        ("servicio", "Servicio"),
    ]

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="items"
    )

    tipo_item = models.CharField(
        max_length=20,
        choices=TIPO_ITEM_CHOICES
    )

    producto = models.ForeignKey(
        "productos.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedido_items"
    )

    servicio = models.ForeignKey(
        "productos.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedido_items"
    )

    nombre_snapshot = models.CharField(
        max_length=255,
        help_text="Nombre del producto/servicio al momento del pedido."
    )

    codigo_snapshot = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Código o SKU al momento del pedido."
    )

    precio_unitario_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    class Meta:
        verbose_name = "Ítem de pedido"
        verbose_name_plural = "Ítems de pedido"
        indexes = [
            models.Index(fields=["tipo_item"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(producto__isnull=False) & models.Q(servicio__isnull=True)) |
                    (models.Q(producto__isnull=True) & models.Q(servicio__isnull=False))
                ),
                name="pedido_item_producto_o_servicio"
            ),
        ]

    def __str__(self):
        return f"{self.nombre_snapshot} x {self.cantidad}"

    def clean(self):
        """
        Valida consistencia del ítem:
        - debe tener producto o servicio, no ambos
        - tipo_item debe coincidir
        """
        if self.producto and self.servicio:
            raise ValidationError("Un ítem no puede tener producto y servicio al mismo tiempo.")

        if not self.producto and not self.servicio:
            raise ValidationError("Un ítem debe tener un producto o un servicio.")

        if self.producto and self.tipo_item != "mercaderia":
            raise ValidationError("Si el ítem tiene producto, tipo_item debe ser 'mercaderia'.")

        if self.servicio and self.tipo_item != "servicio":
            raise ValidationError("Si el ítem tiene servicio, tipo_item debe ser 'servicio'.")

    def save(self, *args, **kwargs):
        """
        Recalcula subtotal del ítem y luego actualiza los totales del pedido.
        """
        self.full_clean()

        self.subtotal = (
            Decimal(self.cantidad) * Decimal(self.precio_unitario_snapshot)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

        # Recalcular pedido después de guardar el item
        self.pedido.recalcular_totales()
        Pedido.objects.filter(pk=self.pedido.pk).update(
            subtotal=self.pedido.subtotal,
            total=self.pedido.total
        )

    def delete(self, *args, **kwargs):
        """
        Al borrar un ítem, recalcula el pedido.
        """
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.recalcular_totales()
        Pedido.objects.filter(pk=pedido.pk).update(
            subtotal=pedido.subtotal,
            total=pedido.total
        )