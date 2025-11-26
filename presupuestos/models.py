# gestion/presupuestos/models.py
import os
import hashlib
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from comprobantes.models import Comprobante
from django.core.exceptions import ValidationError


class Presupuesto(models.Model):
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    comprobante = models.ForeignKey(Comprobante, on_delete=models.PROTECT, null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    valido_hasta = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    condiciones_comerciales = models.TextField(null=True, blank=True)
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=21.00)
    estado = models.CharField(
        max_length=20,
        choices=[("borrador", "Borrador"), ("enviado", "Enviado"), ("aceptado", "Aceptado"), ("rechazado", "Rechazado"), ("anulado", "Anulado")],
        default="borrador"
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    numero = models.PositiveIntegerField(null=True, blank=True)
    
    # Campos para auditoría de anulación
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        null=True, blank=True,
        related_name='presupuestos_anulados'
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)

    # Campos reales en BD para Admin y serializer
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=['comprobante'])]
        ordering = ['-id']  # 👉 ordena automáticamente del más nuevo al más viejo

    def clean(self):
        """Validación de transiciones de estado"""
        if self.pk and self.estado == 'anulado':
            try:
                original = Presupuesto.objects.get(pk=self.pk)
                if original.estado in ['aceptado', 'rechazado']:
                    raise ValidationError(
                        f"No se puede anular un presupuesto que ya está {original.estado}"
                    )
            except Presupuesto.DoesNotExist:
                pass  # Es una creación nueva

    def save(self, *args, **kwargs):
        # Validar transiciones de estado
        if self.pk:  # Solo validar en actualizaciones
            self.clean()
        
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

        # Validar que no exceda el rango máximo permitido por el comprobante
        if self.comprobante and self.numero > self.comprobante.numero_final:
            raise ValidationError(f"No se puede generar el presupuesto. El número {self.numero} excede el límite permitido ({self.comprobante.numero_final}) para este talonario.")

        # Calcular subtotal, IVA y total si ya existen items
        if self.pk:  # solo si es actualización
            self.subtotal = sum((item.subtotal for item in self.items.all()), Decimal('0.00'))
            self.iva_valor = (self.subtotal * self.iva_porcentaje / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.total = (self.subtotal + self.iva_valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

    def __str__(self):
        serie = self.comprobante.serie if self.comprobante else "??"
        numero = f"{self.numero:06d}" if self.numero else "??????"
        estado_str = f" - {self.estado.upper()}" if self.estado == 'anulado' else ""
        return f"Presupuesto {serie}-{numero} - {self.cliente}{estado_str}"

    def anular(self, usuario, motivo=""):
        """Método para anular el presupuesto"""
        if self.estado == 'anulado':
            raise ValidationError("El presupuesto ya está anulado")
        
        if self.estado in ['aceptado', 'rechazado']:
            raise ValidationError(f"No se puede anular un presupuesto que ya está {self.estado}")
        
        self.estado = 'anulado'
        self.anulado_por = usuario
        self.fecha_anulacion = timezone.now()
        self.motivo_anulacion = motivo
        self.save()


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
        # Solo rellenar precio en creación
        if not self.pk and self.precio_unitario in (None, Decimal('0.00'), 0):
            if self.producto:
                self.codigo = self.producto.sku or ''
                self.descripcion = self.producto.nombre
                self.precio_unitario = self.producto.precio_venta or Decimal('0.00')
            elif self.servicio:
                self.codigo = self.servicio.codigo_interno or ''
                self.descripcion = self.servicio.nombre
                self.precio_unitario = self.servicio.precio_base or Decimal('0.00')

        # Agrupación solo en creación
        if not self.pk and not kwargs.get('force_insert', False):
            existente = PresupuestoItem.objects.filter(
                presupuesto=self.presupuesto,
                producto=self.producto,
                servicio=self.servicio
            ).first()
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


class PresupuestoAdjunto(models.Model):
    TIPO_CHOICES = [
        ('plano', '📐 Planos (PDF, DWG)'),
        ('foto', '🖼️ Fotos (referencia, ubicación)'),
        ('diagrama', '📊 Diagramas técnicos'),
        ('contrato', '📝 Contratos/Especificaciones'),
        ('comunicacion', '💬 Comunicaciones relevantes'),
        ('otro', '📎 Otros'),
    ]
   
    presupuesto = models.ForeignKey(
        Presupuesto,
        on_delete=models.CASCADE,
        related_name='adjuntos',
        verbose_name="Presupuesto relacionado"
    )
   
    archivo = models.FileField(
        upload_to='presupuestos/adjuntos/%Y/%m/%d/',
        verbose_name="Archivo adjunto",
        max_length=500  # Ruta larga para organización profunda
    )
   
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='otro',
        verbose_name="Tipo de archivo",
        help_text="Clasificación del archivo para organización"
    )
   
    nombre_original = models.CharField(
        max_length=255,
        verbose_name="Nombre original del archivo",
        help_text="Nombre original al momento de subir"
    )
   
    descripcion = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name="Descripción detallada",
        help_text="Descripción del contenido y propósito del archivo"
    )
   
    tamaño = models.BigIntegerField(
        verbose_name="Tamaño en bytes",
        help_text="Tamaño del archivo en bytes"
    )
   
    extension = models.CharField(
        max_length=10,
        verbose_name="Extensión del archivo",
        help_text="Extensión (pdf, jpg, dwg, etc.)"
    )
   
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Subido por",
        related_name='presupuesto_adjuntos_subidos',
        null=True,
        blank=True
    )
   
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de subida"
    )
   
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última modificación"
    )
   
    # Campos para gestión avanzada
    es_publico = models.BooleanField(
        default=True,
        verbose_name="¿Es público?",
        help_text="Si es False, solo usuarios autorizados pueden verlo"
    )
   
    version = models.PositiveIntegerField(
        default=1,
        verbose_name="Versión del archivo",
        help_text="Número de versión para revisiones"
    )
   
    checksum = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Checksum MD5",
        help_text="Hash para verificar integridad del archivo"
    )
   
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadatos adicionales",
        help_text="Metadatos específicos por tipo de archivo"
    )

    class Meta:
        verbose_name = "Adjunto de presupuesto"
        verbose_name_plural = "Adjuntos de presupuestos"
        ordering = ['-fecha_subida', 'tipo', 'nombre_original']
        indexes = [
            models.Index(fields=['presupuesto', 'tipo']),
            models.Index(fields=['presupuesto', 'fecha_subida']),
            models.Index(fields=['tipo', 'es_publico']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(tamaño__gte=0),
                name='tamaño_archivo_positivo'
            ),
        ]

    def __str__(self):
        return f"{self.nombre_original} ({self.get_tipo_display()}) - {self.presupuesto}"

    def save(self, *args, **kwargs):
        # Calcular tamaño y extensión antes de guardar
        if self.archivo:
            if not self.tamaño:
                self.tamaño = self.archivo.size
           
            if not self.extension:
                self.extension = self.obtener_extension()
           
            if not self.nombre_original:
                self.nombre_original = os.path.basename(self.archivo.name)
       
        # 👇 AGREGAR ESTO: Si no hay usuario asignado y estamos en el contexto de una request
        from django.contrib.auth.models import AnonymousUser
        if not self.subido_por_id and hasattr(self, '_current_user'):
            self.subido_por = self._current_user
        elif not self.subido_por_id:
            # Si no hay usuario disponible, usar el primer superuser o crear uno por defecto
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                default_user = User.objects.filter(is_superuser=True).first()
                if default_user:
                    self.subido_por = default_user
            except:
                pass
       
        super().save(*args, **kwargs)

    def obtener_extension(self):
        """Obtiene la extensión del archivo"""
        if self.archivo:
            return os.path.splitext(self.archivo.name)[1].lower().replace('.', '')
        return ''

    def generar_checksum(self):
        """Genera checksum MD5 del archivo (opcional, puede ser pesado para archivos grandes)"""
        try:
            if self.archivo and hasattr(self.archivo, 'read'):
                return hashlib.md5(self.archivo.read()).hexdigest()
        except (ValueError, IOError):
            pass
        return ''

    def get_tamaño_formateado(self):
        """Devuelve el tamaño formateado (KB, MB, GB)"""
        if self.tamaño == 0:
            return "0 B"
       
        tamanios = ['B', 'KB', 'MB', 'GB']
        i = 0
        tamaño_decimal = float(self.tamaño)
       
        while tamaño_decimal >= 1024.0 and i < len(tamanios) - 1:
            tamaño_decimal /= 1024.0
            i += 1
       
        return f"{tamaño_decimal:.2f} {tamanios[i]}"

    @property
    def url_descarga(self):
        """URL para descargar el archivo"""
        return self.archivo.url if self.archivo else ''

    @property
    def puede_visualizar(self):
        """Determina si el archivo puede ser visualizado en el navegador"""
        extensiones_visualizables = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        return self.extension.lower() in extensiones_visualizables

    def crear_version(self, nuevo_archivo):
        """Crea una nueva versión del archivo"""
        self.version += 1
        self.archivo = nuevo_archivo
        self.tamaño = nuevo_archivo.size
        self.extension = self.obtener_extension()
        self.checksum = self.generar_checksum()
        self.save()