# gestion/backend/pedidos/models.py

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from .emails import enviar_email_estado_pedido
from productos.models import MovimientoStock


class Pedido(models.Model):

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
    )

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos_web",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente"
    )

    observaciones_cliente = models.TextField(blank=True, default="")
    observaciones_internas = models.TextField(blank=True, default="")

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
    stock_reservado_aplicado = models.BooleanField(
        default=False,
        help_text="Indica si este pedido ya aplicó reserva de stock."
    )

    stock_finalizado_aplicado = models.BooleanField(
        default=False,
        help_text="Indica si este pedido ya aplicó salida definitiva o liberación de stock."
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Pedido #{self.id}"

    def recalcular_totales(self):

        subtotal = sum(
            (item.subtotal for item in self.items.all()),
            Decimal("0.00")
        )

        self.subtotal = subtotal.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        self.total = self.subtotal

    def reservar_stock(self):

        if self.stock_reservado_aplicado:
            return

        for item in self.items.select_related("producto"):

            if not item.producto:
                continue

            producto = item.producto

            stock_anterior = producto.stock
            reservado_anterior = producto.stock_reservado

            reservado_nuevo = reservado_anterior + item.cantidad

            if reservado_nuevo > producto.stock:
                raise ValidationError(
                    f"No hay stock disponible para {producto.nombre}"
                )

            producto.stock_reservado = reservado_nuevo

            producto.save(
                update_fields=[
                    "stock_reservado"
                ]
            )

            MovimientoStock.registrar(
                producto=producto,
                tipo="reserva",
                cantidad=item.cantidad,
                stock_anterior=stock_anterior,
                stock_reservado_anterior=reservado_anterior,
                stock_nuevo=producto.stock,
                stock_reservado_nuevo=producto.stock_reservado,
                pedido=self,
                observacion=f"Reserva pedido #{self.id}",
            )

        self.stock_reservado_aplicado = True

        self.save(
            update_fields=[
                "stock_reservado_aplicado"
            ]
        )
    def liberar_stock(self):

        if self.stock_finalizado_aplicado:
            return

        if not self.stock_reservado_aplicado:
            return

        for item in self.items.select_related("producto"):

            if not item.producto:
                continue

            producto = item.producto

            stock_anterior = producto.stock
            reservado_anterior = producto.stock_reservado

            producto.stock_reservado = max(
                0,
                reservado_anterior - item.cantidad
            )

            producto.save(
                update_fields=[
                    "stock_reservado"
                ]
            )

            MovimientoStock.registrar(
                producto=producto,
                tipo="liberacion",
                cantidad=item.cantidad,
                stock_anterior=stock_anterior,
                stock_reservado_anterior=reservado_anterior,
                stock_nuevo=producto.stock,
                stock_reservado_nuevo=producto.stock_reservado,
                pedido=self,
                observacion=f"Liberación pedido #{self.id}",
            )

        self.stock_finalizado_aplicado = True

        self.save(
            update_fields=[
                "stock_finalizado_aplicado"
            ]
        )
    def confirmar_entrega(self):

        if self.stock_finalizado_aplicado:
            return

        for item in self.items.select_related("producto"):

            if not item.producto:
                continue

            producto = item.producto

            stock_anterior = producto.stock
            reservado_anterior = producto.stock_reservado

            producto.stock = max(
                0,
                producto.stock - item.cantidad
            )

            producto.stock_reservado = max(
                0,
                producto.stock_reservado - item.cantidad
            )

            producto.save(
                update_fields=[
                    "stock",
                    "stock_reservado"
                ]
            )

            MovimientoStock.registrar(
                producto=producto,
                tipo="salida",
                cantidad=item.cantidad,
                stock_anterior=stock_anterior,
                stock_reservado_anterior=reservado_anterior,
                stock_nuevo=producto.stock,
                stock_reservado_nuevo=producto.stock_reservado,
                pedido=self,
                observacion=f"Entrega pedido #{self.id}",
            )

        self.stock_finalizado_aplicado = True

        self.save(
            update_fields=[
                "stock_finalizado_aplicado"
            ]
        )

    def save(self, *args, **kwargs):

        estado_anterior = None

        if self.pk:
            try:
                estado_anterior = (
                    Pedido.objects
                    .only("estado")
                    .get(pk=self.pk)
                    .estado
                )
            except Pedido.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if estado_anterior == self.estado:
            return

        if self.estado == "pendiente":
            self.reservar_stock()

        elif self.estado == "confirmado":
            self.reservar_stock()

        elif self.estado == "entregado":
            self.confirmar_entrega()

        elif self.estado == "cancelado":
            self.liberar_stock()

        if self.estado in ["confirmado", "entregado", "cancelado"]:
            try:
                enviar_email_estado_pedido(self)
            except Exception as e:
                print(f"[EMAIL ESTADO PEDIDO] Error enviando email: {e}")

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