# gestion/configuracion/models.py
from django.db import models
from .fields import RedimensionableImageField

class ConfiguracionGlobal(models.Model):
    """Configuración global del sistema con múltiples imágenes"""
   
    # 👇 DATOS BÁSICOS DE EMPRESA
    nombre_empresa = models.CharField(max_length=200, default="Mi Empresa S.A.")
    cuit = models.CharField(max_length=20, blank=True, default="")
    direccion = models.TextField(blank=True, default="")
    telefono = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    pagina_web = models.URLField(blank=True, default="")
   
    # 👇 CONFIGURACIÓN LOGO PRINCIPAL
    logo_principal = RedimensionableImageField(
        upload_to='config/logos/',
        blank=True,
        null=True,
        verbose_name="Logo Principal (Header PDFs)",
        help_text="Logo grande para encabezados de documentos"
    )
    logo_principal_ancho = models.PositiveIntegerField(
        default=800,
        verbose_name="Ancho Logo Principal (px)",
        help_text="Ancho máximo en píxeles"
    )
    logo_principal_alto = models.PositiveIntegerField(
        default=600,
        verbose_name="Alto Logo Principal (px)",
        help_text="Alto máximo en píxeles"
    )
    logo_principal_proporcion = models.BooleanField(
        default=True,
        verbose_name="Mantener proporción",
        help_text="Mantener relación de aspecto original"
    )
   
    # 👇 CONFIGURACIÓN FAVICON
    logo_favicon = RedimensionableImageField(
        upload_to='config/logos/',
        blank=True,
        null=True,
        verbose_name="Favicon (Barra de direcciones)",
        help_text="Icono pequeño para pestañas del navegador"
    )
    logo_favicon_ancho = models.PositiveIntegerField(
        default=32,
        verbose_name="Ancho Favicon (px)",
        help_text="Ancho máximo en píxeles"
    )
    logo_favicon_alto = models.PositiveIntegerField(
        default=32,
        verbose_name="Alto Favicon (px)",
        help_text="Alto máximo en píxeles"
    )
    logo_favicon_proporcion = models.BooleanField(
        default=True,
        verbose_name="Mantener proporción",
        help_text="Mantener relación de aspecto original"
    )
   
    # 👇 CONFIGURACIÓN LOGO TKINTER
    logo_tkinter = RedimensionableImageField(
        upload_to='config/logos/',
        blank=True,
        null=True,
        verbose_name="Logo Tkinter (Interfaz Desktop)",
        help_text="Logo para reemplazar icono por defecto de Tkinter"
    )
    logo_tkinter_ancho = models.PositiveIntegerField(
        default=256,
        verbose_name="Ancho Logo Tkinter (px)",
        help_text="Ancho máximo en píxeles"
    )
    logo_tkinter_alto = models.PositiveIntegerField(
        default=256,
        verbose_name="Alto Logo Tkinter (px)",
        help_text="Alto máximo en píxeles"
    )
    logo_tkinter_proporcion = models.BooleanField(
        default=True,
        verbose_name="Mantener proporción",
        help_text="Mantener relación de aspecto original"
    )
   
    # 👇 CONFIGURACIÓN IMÁGENES PUBLICITARIAS
    imagen_publicitaria_1 = RedimensionableImageField(
        upload_to='config/publicidad/',
        blank=True,
        null=True,
        verbose_name="Imagen Publicitaria 1",
        help_text="Imagen pequeña para pie de página"
    )
    imagen_publicitaria_1_ancho = models.PositiveIntegerField(
        default=400,
        verbose_name="Ancho Imagen 1 (px)",
        help_text="Ancho máximo en píxeles"
    )
    imagen_publicitaria_1_alto = models.PositiveIntegerField(
        default=300,
        verbose_name="Alto Imagen 1 (px)",
        help_text="Alto máximo en píxeles"
    )
    imagen_publicitaria_1_proporcion = models.BooleanField(
        default=True,
        verbose_name="Mantener proporción",
        help_text="Mantener relación de aspecto original"
    )
   
    imagen_publicitaria_2 = RedimensionableImageField(
        upload_to='config/publicidad/',
        blank=True,
        null=True,
        verbose_name="Imagen Publicitaria 2",
        help_text="Imagen pequeña para pie de página"
    )
    imagen_publicitaria_2_ancho = models.PositiveIntegerField(
        default=400,
        verbose_name="Ancho Imagen 2 (px)",
        help_text="Ancho máximo en píxeles"
    )
    imagen_publicitaria_2_alto = models.PositiveIntegerField(
        default=300,
        verbose_name="Alto Imagen 2 (px)",
        help_text="Alto máximo en píxeles"
    )
    imagen_publicitaria_2_proporcion = models.BooleanField(
        default=True,
        verbose_name="Mantener proporción",
        help_text="Mantener relación de aspecto original"
    )
   
    imagen_publicitaria_3 = RedimensionableImageField(
        upload_to='config/publicidad/',
        blank=True,
        null=True,
        verbose_name="Imagen Publicitaria 3",
        help_text="Imagen pequeña para pie de página"
    )
    imagen_publicitaria_3_ancho = models.PositiveIntegerField(
        default=400,
        verbose_name="Ancho Imagen 3 (px)",
        help_text="Ancho máximo en píxeles"
    )
    imagen_publicitaria_3_alto = models.PositiveIntegerField(
        default=300,
        verbose_name="Alto Imagen 3 (px)",
        help_text="Alto máximo en píxeles"
    )
    imagen_publicitaria_3_proporcion = models.BooleanField(
        default=True,
        verbose_name="Mantener proporción",
        help_text="Mantener relación de aspecto original"
    )
   
    # 👇 CONFIGURACIÓN PRESUPUESTOS
    condiciones_comerciales = models.TextField(
        default="""Precios expresados en pesos Argentinos
Plazo de entrega: Inmediata
Forma de Pago: 30 días
Mantenimiento de oferta: 15 días"""
    )
    iva_por_defecto = models.DecimalField(max_digits=5, decimal_places=2, default=21.00)
    dias_validez_presupuesto = models.PositiveIntegerField(default=30)
   
    # 👇 CONFIGURACIÓN GENERAL
    moneda = models.CharField(max_length=10, default="ARS", choices=[('ARS', 'Pesos Argentinos'), ('USD', 'Dólares')])
    pais = models.CharField(max_length=50, default="Argentina")
    idioma = models.CharField(max_length=10, default="es", choices=[('es', 'Español'), ('en', 'Inglés')])
   
    # 👇 METADATA
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración Global"
        verbose_name_plural = "Configuraciones Globales"
    
    def save(self, *args, **kwargs):
        # Solo una configuración activa
        if self.activo:
            ConfiguracionGlobal.objects.exclude(pk=self.pk).update(activo=False)
        
        # Si es una instancia existente y hay imágenes que necesitan reprocesamiento
        if self.pk:
            self.procesar_imagenes_existentes()
        
        super().save(*args, **kwargs)

    def procesar_imagenes_existentes(self):
        """Reprocesa las imágenes existentes si cambiaron las configuraciones"""
        try:
            # Solo procesar si los campos de configuración han cambiado
            campos_configuracion = [
                'logo_principal_ancho', 'logo_principal_alto', 'logo_principal_proporcion',
                'logo_favicon_ancho', 'logo_favicon_alto', 'logo_favicon_proporcion',
                'logo_tkinter_ancho', 'logo_tkinter_alto', 'logo_tkinter_proporcion',
                'imagen_publicitaria_1_ancho', 'imagen_publicitaria_1_alto', 'imagen_publicitaria_1_proporcion',
                'imagen_publicitaria_2_ancho', 'imagen_publicitaria_2_alto', 'imagen_publicitaria_2_proporcion',
                'imagen_publicitaria_3_ancho', 'imagen_publicitaria_3_alto', 'imagen_publicitaria_3_proporcion',
            ]
            
            # Verificar si algún campo de configuración cambió
            if self.pk:
                original = ConfiguracionGlobal.objects.get(pk=self.pk)
                config_cambio = any(
                    getattr(self, campo) != getattr(original, campo) 
                    for campo in campos_configuracion
                )
                
                if config_cambio:
                    self.reprocesar_imagenes()
                    
        except ConfiguracionGlobal.DoesNotExist:
            pass

    def reprocesar_imagenes(self):
        """Reprocesa todas las imágenes existentes con la nueva configuración"""
        from django.core.files.base import ContentFile
        import tempfile
        import os
        
        campos_imagen = [
            ('logo_principal', 'logo_principal'),
            ('logo_favicon', 'logo_favicon'),
            ('logo_tkinter', 'logo_tkinter'),
            ('imagen_publicitaria_1', 'imagen_publicitaria_1'),
            ('imagen_publicitaria_2', 'imagen_publicitaria_2'),
            ('imagen_publicitaria_3', 'imagen_publicitaria_3'),
        ]
        
        for config_key, field_name in campos_imagen:
            imagen_field = getattr(self, field_name)
            if imagen_field and hasattr(imagen_field, 'path') and os.path.exists(imagen_field.path):
                try:
                    # Leer la imagen original
                    with open(imagen_field.path, 'rb') as f:
                        content = ContentFile(f.read())
                    
                    # Usar el mismo método de redimensionamiento
                    content_redimensionado = imagen_field.redimensionar_imagen(content, self)
                    
                    if content_redimensionado != content:
                        # Guardar la imagen redimensionada
                        nombre_archivo = os.path.basename(imagen_field.path)
                        getattr(self, field_name).save(nombre_archivo, content_redimensionado, save=False)
                        
                except Exception as e:
                    print(f"Error reprocesando {field_name}: {e}")

    def actualizar_dimensiones_imagenes(self):
        """Actualiza las dimensiones en los campos de imagen"""
        campos_imagen = [
            ('logo_principal', 'logo_principal_ancho', 'logo_principal_alto'),
            ('logo_favicon', 'logo_favicon_ancho', 'logo_favicon_alto'),
            ('logo_tkinter', 'logo_tkinter_ancho', 'logo_tkinter_alto'),
            ('imagen_publicitaria_1', 'imagen_publicitaria_1_ancho', 'imagen_publicitaria_1_alto'),
            ('imagen_publicitaria_2', 'imagen_publicitaria_2_ancho', 'imagen_publicitaria_2_alto'),
            ('imagen_publicitaria_3', 'imagen_publicitaria_3_ancho', 'imagen_publicitaria_3_alto'),
        ]
        
        for campo_imagen, campo_ancho, campo_alto in campos_imagen:
            imagen_field = getattr(self, campo_imagen)
            if imagen_field:
                imagen_field.field.max_width = getattr(self, campo_ancho)
                imagen_field.field.max_height = getattr(self, campo_alto)
    
    def __str__(self):
        return f"Configuración - {self.nombre_empresa}"
    
    # 👇 PROPIEDADES PARA URLs DE IMÁGENES
    @property
    def logo_principal_url(self):
        if self.logo_principal and hasattr(self.logo_principal, 'url'):
            return self.logo_principal.url
        return None
    
    @property
    def logo_favicon_url(self):
        if self.logo_favicon and hasattr(self.logo_favicon, 'url'):
            return self.logo_favicon.url
        return None
    
    @property
    def logo_tkinter_url(self):
        if self.logo_tkinter and hasattr(self.logo_tkinter, 'url'):
            return self.logo_tkinter.url
        return None
    
    @property
    def imagen_publicitaria_1_url(self):
        if self.imagen_publicitaria_1 and hasattr(self.imagen_publicitaria_1, 'url'):
            return self.imagen_publicitaria_1.url
        return None
    
    @property
    def imagen_publicitaria_2_url(self):
        if self.imagen_publicitaria_2 and hasattr(self.imagen_publicitaria_2, 'url'):
            return self.imagen_publicitaria_2.url
        return None
    
    @property
    def imagen_publicitaria_3_url(self):
        if self.imagen_publicitaria_3 and hasattr(self.imagen_publicitaria_3, 'url'):
            return self.imagen_publicitaria_3.url
        return None
    
    def get_absolute_url(self, request=None):
        """URL absoluta para cualquier imagen"""
        def build_url(url):
            if url and request:
                return request.build_absolute_uri(url)
            return url
        return {
            'logo_principal': build_url(self.logo_principal_url),
            'logo_favicon': build_url(self.logo_favicon_url),
            'logo_tkinter': build_url(self.logo_tkinter_url),
            'imagen_publicitaria_1': build_url(self.imagen_publicitaria_1_url),
            'imagen_publicitaria_2': build_url(self.imagen_publicitaria_2_url),
            'imagen_publicitaria_3': build_url(self.imagen_publicitaria_3_url),
        }