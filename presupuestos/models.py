# gestion/presupuestos/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from comprobantes.models import Comprobante
from django.core.exceptions import ValidationError

class Presupuesto(models.Model):
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    comprobante = models.ForeignKey(Comprobante, on_delete=models.PROTECT, null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    valido_hasta = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    condiciones_comerciales = models.TextField(
        default="Precios expresados en pesos Argentinos\nPlazo de entrega: Inmediata\nForma de Pago: 30 días\nMantenimiento de oferta: 15 días"
    )
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=21.00)
    estado = models.CharField(
        max_length=20,
        choices=[("borrador", "Borrador"), ("enviado", "Enviado"), ("aceptado", "Aceptado"), ("rechazado", "Rechazado")],
        default="borrador"
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    numero = models.PositiveIntegerField(null=True, blank=True)

    # Campos reales en BD para Admin y serializer
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=['comprobante'])]
        ordering = ['-id']  # 👉 ordena automáticamente del más nuevo al más viejo

    def save(self, *args, **kwargs):
        # Asignar comprobante si no tiene
        if not self.comprobante:
            comprobante = Comprobante.objects.filter(tipo="PRES").first()
            if not comprobante:
                raise ValidationError("No hay comprobante de tipo PRES configurado.")
            self.comprobante = comprobante

        # Asignar número si no tiene
        if not self.numero:
            ultimo = Presupuesto.objects.filter(comprobante=self.comprobante).order_by('-numero').first()
            self.numero = (ultimo.numero + 1) if ultimo and ultimo.numero else self.comprobante.numero_comienzo

        # Calcular subtotal, IVA y total si ya existen items
        if self.pk:  # solo si es actualización
            self.subtotal = sum((item.subtotal for item in self.items.all()), Decimal('0.00'))
            self.iva_valor = (self.subtotal * self.iva_porcentaje / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.total = (self.subtotal + self.iva_valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

    def __str__(self):
        serie = self.comprobante.serie if self.comprobante else "??"
        numero = f"{self.numero:06d}" if self.numero else "??????"
        return f"Presupuesto {serie}-{numero} - {self.cliente}"


class PresupuestoItem(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, related_name="items", on_delete=models.CASCADE)
    producto = models.ForeignKey("productos.Producto", null=True, blank=True, on_delete=models.PROTECT)
    servicio = models.ForeignKey("productos.Servicio", null=True, blank=True, on_delete=models.PROTECT)
    codigo = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(producto__isnull=False) & models.Q(servicio__isnull=True)) |
                      (models.Q(producto__isnull=True) & models.Q(servicio__isnull=False)),
                name='presupuesto_item_producto_or_servicio'
            )
        ]

    def save(self, *args, **kwargs):
        # Llenar automáticamente código, descripción y precio
        if self.producto:
            self.codigo = self.producto.sku or ''
            self.descripcion = self.producto.nombre
            self.precio_unitario = self.producto.precio_venta or Decimal('0.00')
        elif self.servicio:
            self.codigo = self.servicio.codigo_interno or ''
            self.descripcion = self.servicio.nombre
            if not self.precio_unitario or self.precio_unitario == 0:
                self.precio_unitario = self.servicio.precio_base or Decimal('0.00')

        # Sumar cantidades si ya existe item igual
        if not kwargs.get('force_insert', False):
            existente = PresupuestoItem.objects.filter(
                presupuesto=self.presupuesto,
                producto=self.producto,
                servicio=self.servicio
            ).exclude(pk=self.pk).first()
            if existente:
                existente.cantidad += self.cantidad
                existente.save()
                return

        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.cantidad * self.precio_unitario).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def __str__(self):
        if self.producto:
            return f"{self.codigo} - {self.producto.nombre} x {self.cantidad}"
        elif self.servicio:
            return f"{self.codigo} - {self.servicio.nombre} x {self.cantidad}"
        return f"Item sin referencia (ID {self.id})"
