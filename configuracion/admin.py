# gestion/configuracion/admin.py
from django.contrib import admin
from .models import ConfiguracionGlobal
from django.utils.html import format_html

@admin.register(ConfiguracionGlobal)
class ConfiguracionGlobalAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'nombre_fantasia', 'proximo_numero_presupuesto_display', 'activo', 'creado', 'actualizado')
    list_filter = ('activo', 'pais', 'moneda')
    search_fields = ('nombre_empresa', 'nombre_fantasia', 'cuit', 'email')
    
    # ⭐⭐ NUEVO: Acciones personalizadas
    actions = ['sincronizar_con_comprobante', 'resetear_numeracion']
   
    fieldsets = (
        ('📋 Datos de la Empresa', {
            'fields': (
                'nombre_empresa', 'nombre_fantasia', 'descripcion_sistema', 'cuit', 'direccion',
                'telefono', 'email', 'pagina_web'
            )
        }),
        
        ('📄 Configuración Presupuestos', {
            'fields': (
                'condiciones_comerciales',
                'iva_por_defecto',
                'dias_validez_presupuesto',
                # ⭐⭐ NUEVO: Campo de próximo número
                'proximo_numero_presupuesto'
            ),
            'description': 'Configuración específica para presupuestos'
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
        
        ('⚙️ Configuración General', {
            'fields': (
                'moneda', 'pais', 'idioma', 'activo'
            )
        }),
        
        ('📊 Estado de Sincronización', {
            'fields': ('estado_sincronizacion_display',),
            'classes': ('collapse',),
            'description': 'Información sobre la sincronización con Comprobante'
        }),
    )
    
    # ⭐⭐ NUEVO: Método para mostrar el próximo número con formato
    def proximo_numero_presupuesto_display(self, obj):
        """Muestra el próximo número con color según estado"""
        if not obj.proximo_numero_presupuesto:
            return format_html('<span style="color: gray;">No configurado</span>')
        
        # Obtener estado de sincronización
        estado = obj.estado_sincronizacion_numeracion()
        
        if estado['sincronizado']:
            color = "green"
            icon = "✅"
        else:
            color = "orange"
            icon = "⚠️"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>',
            color,
            icon,
            obj.proximo_numero_presupuesto
        )
    proximo_numero_presupuesto_display.short_description = "Próximo N°"
    
    # ⭐⭐ NUEVO: Método para mostrar estado de sincronización
    def estado_sincronizacion_display(self, obj):
        """Muestra el estado de sincronización con Comprobante"""
        estado = obj.estado_sincronizacion_numeracion()
        
        if not estado['sincronizado']:
            if estado['comprobante'] is None:
                return format_html(
                    '<div style="background-color: #ffebee; padding: 10px; border-radius: 5px;">'
                    '<strong style="color: #d32f2f;">❌ ERROR</strong><br>'
                    'No hay comprobante PRES configurado.<br>'
                    'Configuración: <strong>{}</strong>'
                    '</div>',
                    estado['configuracion']
                )
            else:
                return format_html(
                    '<div style="background-color: #fff3e0; padding: 10px; border-radius: 5px;">'
                    '<strong style="color: #f57c00;">⚠️ DESINCRONIZADO</strong><br>'
                    'Configuración: <strong>{}</strong><br>'
                    'Comprobante: <strong>{}</strong><br>'
                    'Rango comprobante: <strong>{}</strong>'
                    '</div>',
                    estado['configuracion'],
                    estado['comprobante'],
                    estado.get('rango_comprobante', 'N/A')
                )
        else:
            return format_html(
                '<div style="background-color: #e8f5e9; padding: 10px; border-radius: 5px;">'
                '<strong style="color: #388e3c;">✅ SINCRONIZADO</strong><br>'
                'Configuración: <strong>{}</strong><br>'
                'Comprobante: <strong>{}</strong><br>'
                'Rango comprobante: <strong>{}</strong>'
                '</div>',
                estado['configuracion'],
                estado['comprobante'],
                estado.get('rango_comprobante', 'N/A')
            )
    estado_sincronizacion_display.short_description = "Estado de Sincronización"
   
    readonly_fields = ('creado', 'actualizado', 'estado_sincronizacion_display')
   
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
    
    # ⭐⭐ NUEVA: Acción para sincronizar manualmente
    def sincronizar_con_comprobante(self, request, queryset):
        """Sincroniza manualmente con Comprobante"""
        success_count = 0
        error_count = 0
        
        for config in queryset:
            try:
                if config.sincronizar_con_comprobante():
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error sincronizando {config.nombre_empresa}: {e}",
                    level='error'
                )
                error_count += 1
        
        if success_count > 0:
            self.message_user(
                request,
                f"{success_count} configuraciones sincronizadas correctamente",
                level='success'
            )
        
        if error_count > 0:
            self.message_user(
                request,
                f"{error_count} configuraciones no se pudieron sincronizar",
                level='warning'
            )
    
    sincronizar_con_comprobante.short_description = "🔄 Sincronizar con Comprobante"
    
    # ⭐⭐ NUEVA: Acción para resetear numeración
    def resetear_numeracion(self, request, queryset):
        """Resetea el próximo número a 1"""
        for config in queryset:
            config.proximo_numero_presupuesto = 1
            config.save()
        
        self.message_user(
            request,
            f"{queryset.count()} configuraciones reseteadas a 1",
            level='success'
        )
    
    resetear_numeracion.short_description = "🔄 Resetear numeración a 1"
    
    # ⭐⭐ NUEVO: Sobreescribir save_model para sincronizar automáticamente
    def save_model(self, request, obj, form, change):
        """Guardar modelo y sincronizar automáticamente"""
        # Guardar primero
        super().save_model(request, obj, form, change)
        
        # Si se cambió el próximo número, sincronizar
        if 'proximo_numero_presupuesto' in form.changed_data:
            obj.sincronizar_con_comprobante()
            self.message_user(
                request,
                f"Próximo número actualizado a {obj.proximo_numero_presupuesto} y sincronizado con Comprobante",
                level='success'
            )