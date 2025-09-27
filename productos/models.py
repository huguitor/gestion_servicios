# gestion/productos/models.py
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.core.validators import MinValueValidator

class Producto(models.Model):
    sku = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Código interno (se genera automáticamente si se deja vacío)."
    )
    codigo_barras = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True)

    precio_venta = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    costo_compra = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)]
    )

    stock = models.PositiveIntegerField(default=0)
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.PROTECT, blank=True, null=True)
    categoria = models.ForeignKey('categorias.Categoria', on_delete=models.PROTECT, blank=True, null=True)
    marca = models.ForeignKey('marcas.Marca', on_delete=models.PROTECT, blank=True, null=True)

    impuestos = models.ManyToManyField('impuestos.Impuesto', through='ProductoImpuesto', blank=True)
    foto = models.ImageField(upload_to="productos/fotos/", blank=True, null=True)
    plano = models.FileField(upload_to="productos/planos/", blank=True, null=True)

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['sku', 'codigo_barras'])]
        ordering = ['sku', 'nombre']

    def __str__(self):
        return f"{self.sku or 'NO-SKU'} - {self.nombre}"

    def save(self, *args, **kwargs):
        if not self.sku:
            last = Producto.objects.all().order_by('id').last()
            next_id = (last.id + 1) if last else 1
            self.sku = f"P{next_id:05d}"
        super().save(*args, **kwargs)

    def _impuestos_queryset(self, tipo='venta'):
        return self.productoimpuesto_set.filter(tipo=tipo)

    def impuestos_dict(self, tipo='venta'):
        res = {}
        for pip in self._impuestos_queryset(tipo=tipo).select_related('impuesto'):
            res[pip.impuesto.nombre] = Decimal(str(pip.impuesto.porcentaje))
        return res

    def precio_venta_con_impuestos(self):
        if self.precio_venta is None:
            return None
        impuestos = self.impuestos_dict(tipo='venta')
        if not impuestos:
            return Decimal(self.precio_venta).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_pct = sum(impuestos.values())
        total = Decimal(self.precio_venta) * (Decimal('1') + total_pct / Decimal('100'))
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def costo_compra_con_impuestos(self):
        if self.costo_compra is None:
            return None
        impuestos = self.impuestos_dict(tipo='compra')
        if not impuestos:
            return Decimal(self.costo_compra).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_pct = sum(impuestos.values())
        total = Decimal(self.costo_compra) * (Decimal('1') + total_pct / Decimal('100'))
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class Servicio(models.Model):
    codigo_interno = models.CharField(
        max_length=50, unique=True, blank=True, null=True, help_text="Código interno (S00001...)"
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)

    costo_base = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    precio_base = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )

    categoria = models.ForeignKey('categorias.Categoria', on_delete=models.PROTECT, blank=True, null=True)
    marca = models.ForeignKey('marcas.Marca', on_delete=models.PROTECT, blank=True, null=True)
    impuestos = models.ManyToManyField('impuestos.Impuesto', through='ServicioImpuesto', blank=True)
    imagen = models.ImageField(upload_to="servicios/imagenes/", blank=True, null=True)
    adjunto = models.FileField(upload_to="servicios/adjuntos/", blank=True, null=True)

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['codigo_interno'])]
        ordering = ['codigo_interno', 'nombre']

    def __str__(self):
        return f"{self.codigo_interno or 'NO-CODE'} - {self.nombre}"

    def save(self, *args, **kwargs):
        if not self.codigo_interno:
            last = Servicio.objects.all().order_by('id').last()
            next_id = (last.id + 1) if last else 1
            self.codigo_interno = f"S{next_id:05d}"
        super().save(*args, **kwargs)

    def impuestos_dict(self, tipo='venta'):
        res = {}
        for sip in self.servicioimpuesto_set.filter(tipo=tipo).select_related('impuesto'):
            res[sip.impuesto.nombre] = Decimal(str(sip.impuesto.porcentaje))
        return res

    def precio_base_con_impuestos(self):
        if self.precio_base is None:
            return None
        impuestos = self.impuestos_dict(tipo='venta')
        if not impuestos:
            return Decimal(self.precio_base).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_pct = sum(impuestos.values())
        total = Decimal(self.precio_base) * (Decimal('1') + total_pct / Decimal('100'))
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class ProductoImpuesto(models.Model):
    TIPO_CHOICES = [
        ('compra', 'Compra'),
        ('venta', 'Venta'),
    ]
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    impuesto = models.ForeignKey('impuestos.Impuesto', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)

    class Meta:
        unique_together = ('producto', 'impuesto', 'tipo')

    def __str__(self):
        return f"{self.producto.nombre} - {self.impuesto.nombre} ({self.tipo})"

class ServicioImpuesto(models.Model):
    TIPO_CHOICES = [
        ('compra', 'Compra'),
        ('venta', 'Venta'),
    ]
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    impuesto = models.ForeignKey('impuestos.Impuesto', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)

    class Meta:
        unique_together = ('servicio', 'impuesto', 'tipo')

    def __str__(self):
        return f"{self.servicio.nombre} - {self.impuesto.nombre} ({self.tipo})"