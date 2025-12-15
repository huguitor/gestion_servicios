# gestion/remitos/models.py
import os
import hashlib
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from comprobantes.models import Comprobante


class Remito(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente'),
        ('entregado', 'Entregado'),
        ('anulado', 'Anulado'),
    ]
   
    # ⭐ NUMERACIÓN AUTOMÁTICA (IGUAL QUE PRESUPUESTOS)
    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,
        limit_choices_to={'tipo': 'REMI'},
        help_text="Configuración de numeración para remitos"
    )
    numero = models.PositiveIntegerField(null=True, blank=True, editable=False)
   
    # ⭐ DATOS BÁSICOS - IGUAL QUE PRESUPUESTOS
    cliente = models.ForeignKey(
        'clientes.Cliente',
        on_delete=models.PROTECT,
        verbose_name="Cliente/Destinatario"
    )
    fecha_emision = models.DateField(default=timezone.now, verbose_name="Fecha de emisión")
    fecha_entrega = models.DateField(null=True, blank=True, verbose_name="Fecha de entrega")
   
    # ⭐ ORIGEN Y DESTINO (ESPECÍFICO PARA REMITOS)
    origen = models.CharField(max_length=200, blank=True, verbose_name="Desde")
    destino = models.CharField(max_length=200, blank=True, verbose_name="Hacia")
   
    # ⭐ REFERENCIAS (ESPECÍFICO PARA REMITOS)
    presupuesto_relacionado = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° de presupuesto"
    )
    licitacion_orden = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Licitación/Orden de compra"
    )
    numero_referencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="N° de referencia"
    )
   
    # ⭐ OBSERVACIONES
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
   
    # ⭐ ESTADO
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='borrador'
    )
   
    # ⭐ AUDITORÍA - IGUAL QUE PRESUPUESTOS
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Creado por"
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
   
    # ⭐ CAMPOS PARA ANULACIÓN - IGUAL QUE PRESUPUESTOS
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='remitos_anulados',
        verbose_name="Anulado por"
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)


    class Meta:
        ordering = ['-id']
        verbose_name = 'Remito'
        verbose_name_plural = 'Remitos'


    def clean(self):
        """Validación de transiciones de estado"""
        if self.pk and self.estado == 'anulado':
            try:
                original = Remito.objects.get(pk=self.pk)
                if original.estado == 'entregado':
                    raise ValidationError("No se puede anular un remito ya entregado")
            except Remito.DoesNotExist:
                pass


    def save(self, *args, **kwargs):
        # Validar transiciones de estado
        if self.pk:  # Solo validar en actualizaciones
            self.clean()
       
        # Asignar comprobante si no tiene
        if not self.comprobante:
            comprobante = Comprobante.objects.filter(tipo="REMI").first()
            if not comprobante:
                raise ValidationError("No hay comprobante de tipo REMI configurado.")
            self.comprobante = comprobante


        # ⭐⭐ LÓGICA DE NUMERACIÓN - EXACTAMENTE IGUAL QUE PRESUPUESTOS
        if not self.numero:
            # 1. Usar el próximo número configurado en el comprobante
            self.numero = self.comprobante.proximo_numero
           
            # 2. Validar que no exceda el límite actual
            if self.numero > self.comprobante.numero_final:
                raise ValidationError(
                    f"❌ Límite de numeración alcanzado ({self.comprobante.numero_final}).\n"
                    f"Quedan 0 números disponibles.\n"
                    f"Por favor, amplía el rango en Configuración → Comprobantes."
                )
           
            # 3. ACTUALIZAR el próximo número para futuros remitos
            self.comprobante.proximo_numero += 1
            self.comprobante.save()


        super().save(*args, **kwargs)


    def __str__(self):
        serie = self.comprobante.serie if self.comprobante else "??"
        numero = f"{self.numero:06d}" if self.numero else "??????"
        estado_str = f" - {self.estado.upper()}" if self.estado == 'anulado' else ""
       
        # Mostrar nombre del cliente (como presupuestos)
        if hasattr(self.cliente, 'nombre'):
            cliente_nombre = f"{self.cliente.nombre} {getattr(self.cliente, 'apellido', '')}".strip()
        else:
            cliente_nombre = str(self.cliente)
       
        return f"Remito {serie}-{numero} - {cliente_nombre}{estado_str}"


    def anular(self, usuario, motivo=""):
        """Método para anular el remito - IGUAL QUE PRESUPUESTOS"""
        if self.estado == 'anulado':
            raise ValidationError("El remito ya está anulado")
       
        if self.estado == 'entregado':
            raise ValidationError("No se puede anular un remito entregado")
       
        self.estado = 'anulado'
        self.anulado_por = usuario
        self.fecha_anulacion = timezone.now()
        self.motivo_anulacion = motivo
        self.save()


    @property
    def numero_formateado(self):
        """Devuelve el número formateado - MEJORADO"""
        if self.comprobante and self.numero:
            serie = self.comprobante.serie
            return f"{serie}-{self.numero:06d}"
        return "Sin número"


    # ⭐ MÉTODO ÚTIL COMO PRESUPUESTOS
    @property
    def numeros_disponibles_restantes(self):
        """Muestra cuántos números quedan después de este remito"""
        if self.comprobante:
            return self.comprobante.numeros_disponibles - 1  # -1 porque este ya usó uno
        return 0

    # ⭐ MÉTODO PARA ADMIN - COMPATIBILIDAD
    def cliente_nombre(self):
        """Método para admin.py - Devuelve nombre del cliente"""
        if self.cliente and hasattr(self.cliente, 'nombre'):
            return f"{self.cliente.nombre} {getattr(self.cliente, 'apellido', '')}".strip()
        return str(self.cliente)
    cliente_nombre.short_description = 'Cliente'  # Para admin


class ItemRemito(models.Model):
    """Items editables del remito"""
    remito = models.ForeignKey(
        Remito,
        related_name="items",
        on_delete=models.CASCADE
    )
   
    # ⭐ CAMPOS EDITABLES
    codigo = models.CharField(max_length=50, blank=True, verbose_name="Código")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
        verbose_name="Cantidad"
    )
    unidad_medida = models.CharField(
        max_length=20,
        default='UNIDAD',
        verbose_name="Unidad de medida"
    )
   
    # ⭐ OBSERVACIONES DEL ÍTEM
    observaciones = models.TextField(blank=True, verbose_name="Observaciones del ítem")
   
    # ⭐ ORDEN
    orden = models.IntegerField(default=0)


    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'Item de remito'
        verbose_name_plural = 'Items de remito'


    def __str__(self):
        return f"{self.codigo or 'Sin código'} - {self.descripcion[:50]} x {self.cantidad}"
    
    @property
    def subtotal(self):
        """Propiedad calculada para admin y serializers"""
        return self.cantidad  # En remitos no hay precio, solo cantidad


class RemitoAdjunto(models.Model):
    TIPO_CHOICES = [
        ('entrega', '📦 Comprobante de entrega'),
        ('firma', '✍️ Firma del cliente'),
        ('foto', '🖼️ Foto del producto/servicio'),
        ('documento', '📄 Documentación adicional'),
        ('otro', '📎 Otros'),
    ]
    
    remito = models.ForeignKey(
        Remito,
        on_delete=models.CASCADE,
        related_name='adjuntos'
    )
    
    archivo = models.FileField(
        upload_to='remitos/adjuntos/%Y/%m/%d/',
        verbose_name="Archivo adjunto"
    )
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='otro'
    )
    
    nombre_original = models.CharField(
        max_length=255,
        blank=True
    )
    
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    
    tamaño = models.BigIntegerField(
        default=0,
        verbose_name="Tamaño en bytes"
    )
    
    extension = models.CharField(
        max_length=10,
        blank=True
    )
    
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Adjunto de remito"
        verbose_name_plural = "Adjuntos de remito"
        ordering = ['-fecha_subida']
    
    def __str__(self):
        return f"Adjunto: {self.nombre_original or self.archivo.name}"
    
    def save(self, *args, **kwargs):
        import os
        
        if self.archivo:
            if not self.nombre_original:
                self.nombre_original = os.path.basename(self.archivo.name)
            
            if not self.extension:
                self.extension = os.path.splitext(self.archivo.name)[1].lower().replace('.', '')
            
            if not self.tamaño:
                self.tamaño = self.archivo.size
        
        super().save(*args, **kwargs)
    
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