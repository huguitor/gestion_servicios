# gestion/configuracion/admin.py
from django.contrib import admin
from .models import ConfiguracionGlobal
from django.utils.html import format_html, mark_safe


@admin.register(ConfiguracionGlobal)
class ConfiguracionGlobalAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'nombre_fantasia', 'activo_display', 'creado', 'actualizado')
    list_filter = ('activo', 'pais', 'moneda')
    search_fields = ('nombre_empresa', 'nombre_fantasia', 'cuit', 'email')
   
    # ⭐⭐ NOTA: Ya no hay acciones de sincronización con Comprobante
    actions = []  # Sin acciones relacionadas con numeración
   
    fieldsets = (
        ('📋 Datos de la Empresa', {
            'fields': (
                'nombre_empresa', 'nombre_fantasia', 'descripcion_sistema', 'cuit', 'direccion',
                'telefono', 'email', 'pagina_web'
            )
        }),
       
        ('📄 Configuración de Presupuestos', {
            'fields': (
                'condiciones_comerciales',
                'iva_por_defecto',
                'dias_validez_presupuesto',
            ),
            'description': mark_safe(
                'Configuración específica para presupuestos<br>'
                '⚠️ <strong>La numeración de presupuestos ahora se maneja desde la app "Comprobantes"</strong><br>'
                '↳ Ver: <strong>Comprobantes → Tipo: PRES, Serie: 00001</strong>'
            )
        }),
       
        ('🖼️ Logo Principal (Header PDFs)', {
            'fields': (
                'logo_principal',
                ('logo_principal_ancho', 'logo_principal_alto', 'logo_principal_proporcion'),
            ),
            'description': 'Logo grande para encabezados de documentos PDF'
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
       
        ('📊 Información del Sistema', {
            'fields': ('informacion_sistema',),
            'classes': ('collapse',),
            'description': 'Información sobre el estado del sistema'
        }),
    )
   
    # ⭐⭐ NUEVO: Método para mostrar el estado activo con colores
    def activo_display(self, obj):
        """Muestra el estado activo con colores"""
        if obj.activo:
            return format_html(
                '<span style="background-color: #4CAF50; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-weight: bold;">✅ ACTIVO</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #9E9E9E; color: white; padding: 3px 8px; '
                'border-radius: 4px;">⏸️ INACTIVO</span>'
            )
    activo_display.short_description = "Estado"
   
    # ⭐⭐ NUEVO: Campo informativo para el sistema
    def informacion_sistema(self, obj):
        """Información sobre el sistema y la numeración"""
        try:
            from comprobantes.models import Comprobante
            
            # Verificar si existe el comprobante para presupuestos
            comprobante_pres = Comprobante.objects.filter(tipo='PRES', serie='00001').first()
            
            if comprobante_pres:
                info = format_html(
                    '<div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 5px solid #4CAF50;">'
                    '<h4 style="margin-top: 0; color: #388e3c;">✅ Sistema de Numeración Activo</h4>'
                    '<p><strong>Comprobante PRES-00001:</strong> ID {}</p>'
                    '<p><strong>Próximo número:</strong> {}</p>'
                    '<p><strong>Rango configurado:</strong> {:,} - {:,}</p>'
                    '<hr style="margin: 10px 0;">'
                    '<p><small>ℹ️ La numeración de presupuestos se maneja exclusivamente desde '
                    '<strong>Comprobantes → Tipo: PRES, Serie: 00001</strong></small></p>'
                    '</div>',
                    comprobante_pres.id,
                    comprobante_pres.proximo_numero,
                    comprobante_pres.numero_inicial,
                    comprobante_pres.numero_final
                )
            else:
                info = format_html(
                    '<div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; border-left: 5px solid #ff9800;">'
                    '<h4 style="margin-top: 0; color: #f57c00;">⚠️ Sistema de Numeración Incompleto</h4>'
                    '<p>No se encontró el comprobante para presupuestos.</p>'
                    '<p>Por favor, cree un comprobante en <strong>Comprobantes</strong> con:</p>'
                    '<ul>'
                    '<li><strong>Tipo:</strong> PRES</li>'
                    '<li><strong>Serie:</strong> 00001</li>'
                    '<li><strong>Próximo número:</strong> 1 (o según necesite)</li>'
                    '</ul>'
                    '<hr style="margin: 10px 0;">'
                    '<p><small>ℹ️ Sin este comprobante, no se podrán crear nuevos presupuestos.</small></p>'
                    '</div>'
                )
            
            return info
        
        except ImportError:
            return format_html(
                '<div style="background-color: #ffebee; padding: 15px; border-radius: 5px; border-left: 5px solid #f44336;">'
                '<h4 style="margin-top: 0; color: #d32f2f;">❌ Error en el Sistema</h4>'
                '<p>No se puede acceder a la app "comprobantes".</p>'
                '<p>Verifique que la app esté instalada y configurada correctamente.</p>'
                '</div>'
            )
    
    informacion_sistema.short_description = "Información del Sistema"
   
    readonly_fields = ('creado', 'actualizado', 'informacion_sistema')
   
    def has_add_permission(self, request):
        """Permitir agregar solo si no hay configuraciones activas"""
        if ConfiguracionGlobal.objects.filter(activo=True).exists():
            return False
        return True
   
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar la configuración activa"""
        if obj and obj.activo:
            return False
        return True
   
    # ⭐⭐ NOTA: Ya no hay métodos para sincronizar con Comprobante
    # ⭐⭐ NOTA: Ya no hay método save_model con sincronización automática
   
    # ⭐⭐ NUEVO: Información sobre la configuración en el listado
    def get_queryset(self, request):
        """Optimizar consultas en el listado"""
        return super().get_queryset(request).select_related()
   
    # ⭐⭐ NUEVO: Mensaje de ayuda en la página de cambio
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Agregar contexto adicional a la vista de edición"""
        extra_context = extra_context or {}
        
        # Obtener información del comprobante para mostrar como ayuda
        try:
            from comprobantes.models import Comprobante
            comprobante = Comprobante.objects.filter(tipo='PRES', serie='00001').first()
            
            if comprobante:
                extra_context['comprobante_info'] = {
                    'existe': True,
                    'id': comprobante.id,
                    'proximo_numero': comprobante.proximo_numero,
                    'tipo': comprobante.tipo,
                    'serie': comprobante.serie,
                }
            else:
                extra_context['comprobante_info'] = {
                    'existe': False,
                    'mensaje': 'No se encontró comprobante PRES-00001'
                }
        except ImportError:
            extra_context['comprobante_info'] = {
                'existe': False,
                'mensaje': 'Error al acceder a la app comprobantes'
            }
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)