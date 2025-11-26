# gestion/configuracion/admin.py
from django.contrib import admin
from .models import ConfiguracionGlobal

@admin.register(ConfiguracionGlobal)
class ConfiguracionGlobalAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'nombre_fantasia', 'descripcion_sistema', 'activo', 'creado', 'actualizado')
    list_filter = ('activo', 'pais', 'moneda')
    search_fields = ('nombre_empresa', 'nombre_fantasia', 'cuit', 'email')
   
    fieldsets = (
        ('📋 Datos de la Empresa', {
            'fields': (
                'nombre_empresa', 'nombre_fantasia', 'descripcion_sistema', 'cuit', 'direccion',
                'telefono', 'email', 'pagina_web'
            )
        }),
        
        ('🖼️ Logo Principal (Header PDFs)', {
            'fields': (
                'logo_principal',
                ('logo_principal_ancho', 'logo_principal_alto', 'logo_principal_proporcion'),
            ),
            'description': 'Configuración del logo principal para documentos PDF'
        }),
        
        ('🌐 Favicon (Barra de direcciones)', {
            'fields': (
                'logo_favicon',
                ('logo_favicon_ancho', 'logo_favicon_alto', 'logo_favicon_proporcion'),
            ),
            'description': 'Icono pequeño para pestañas del navegador'
        }),
        
        ('💻 Logo Tkinter (Interfaz Desktop)', {
            'fields': (
                'logo_tkinter',
                ('logo_tkinter_ancho', 'logo_tkinter_alto', 'logo_tkinter_proporcion'),
            ),
            'description': 'Logo para reemplazar icono por defecto de Tkinter (se usa en el login)'
        }),
        
        ('📢 Imágenes Publicitarias - Imagen 1', {
            'fields': (
                'imagen_publicitaria_1',
                ('imagen_publicitaria_1_ancho', 'imagen_publicitaria_1_alto', 'imagen_publicitaria_1_proporcion'),
            )
        }),
        
        ('📢 Imágenes Publicitarias - Imagen 2', {
            'fields': (
                'imagen_publicitaria_2',
                ('imagen_publicitaria_2_ancho', 'imagen_publicitaria_2_alto', 'imagen_publicitaria_2_proporcion'),
            )
        }),
        
        ('📢 Imágenes Publicitarias - Imagen 3', {
            'fields': (
                'imagen_publicitaria_3',
                ('imagen_publicitaria_3_ancho', 'imagen_publicitaria_3_alto', 'imagen_publicitaria_3_proporcion'),
            )
        }),
        
        ('📄 Configuración Presupuestos', {
            'fields': (
                'condiciones_comerciales',
                'iva_por_defecto',
                'dias_validez_presupuesto'
            )
        }),
        
        ('⚙️ Configuración General', {
            'fields': (
                'moneda', 'pais', 'idioma', 'activo'
            )
        }),
    )
   
    readonly_fields = ('creado', 'actualizado')
   
    def has_add_permission(self, request):
        # Permitir agregar solo si no hay configuraciones activas
        if ConfiguracionGlobal.objects.filter(activo=True).exists():
            return False
        return True
   
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar la configuración activa
        if obj and obj.activo:
            return False
        return True