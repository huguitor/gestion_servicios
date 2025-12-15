# gestion/remitos/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Remito, ItemRemito, RemitoAdjunto


class ItemRemitoInline(admin.TabularInline):
    model = ItemRemito
    extra = 0
    fields = ('codigo', 'descripcion', 'cantidad', 'unidad_medida', 'observaciones', 'orden')
    show_change_link = True


class RemitoAdjuntoInline(admin.TabularInline):
    model = RemitoAdjunto
    extra = 0
    fields = ('archivo', 'tipo', 'descripcion', 'get_tamaño_formateado')
    readonly_fields = ('get_tamaño_formateado',)
    show_change_link = True
    
    def get_tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()
    get_tamaño_formateado.short_description = 'Tamaño'


@admin.register(Remito)
class RemitoAdmin(admin.ModelAdmin):
    list_display = ('numero_formateado', 'cliente_nombre', 'fecha_emision', 'estado_display', 'presupuesto_relacionado')
    list_filter = ('estado', 'fecha_emision', 'comprobante__serie')
    search_fields = ('numero_formateado', 'cliente__nombre', 'presupuesto_relacionado', 'licitacion_orden')
    readonly_fields = ('numero_formateado', 'creado_por', 'creado', 'actualizado', 'numero')
    inlines = [ItemRemitoInline, RemitoAdjuntoInline]
    
    fieldsets = (
        ('Numeración', {
            'fields': ('comprobante', 'numero_formateado')
        }),
        ('Información del Remito', {
            'fields': (
                'cliente',
                ('fecha_emision', 'fecha_entrega'),
                ('origen', 'destino'),
            )
        }),
        ('Referencias', {
            'fields': (
                'presupuesto_relacionado',
                ('licitacion_orden', 'numero_referencia'),
            )
        }),
        ('Estado y Observaciones', {
            'fields': ('estado', 'observaciones')
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'creado', 'actualizado'),
            'classes': ('collapse',)
        }),
        ('Anulación', {
            'fields': ('anulado_por', 'fecha_anulacion', 'motivo_anulacion'),
            'classes': ('collapse',)
        }),
    )
    
    def cliente_nombre(self, obj):
        """Muestra el nombre del cliente en la lista"""
        if obj.cliente and hasattr(obj.cliente, 'nombre'):
            return f"{obj.cliente.nombre} {getattr(obj.cliente, 'apellido', '')}".strip()
        return str(obj.cliente)
    cliente_nombre.short_description = 'Cliente'
    cliente_nombre.admin_order_field = 'cliente__nombre'
    
    def estado_display(self, obj):
        """Muestra el estado con colores"""
        color_map = {
            'borrador': 'gray',
            'pendiente': 'orange',
            'entregado': 'green',
            'anulado': 'red'
        }
        color = color_map.get(obj.estado, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_display.short_description = 'Estado'
    
    def get_readonly_fields(self, request, obj=None):
        """Campos de solo lectura según el estado"""
        readonly_fields = list(self.readonly_fields)
        
        if obj:  # Si es una edición (no creación)
            # Si el remito está anulado o entregado, hacer más campos readonly
            if obj.estado in ['anulado', 'entregado']:
                readonly_fields.extend(['cliente', 'comprobante', 'estado', 'items'])
        
        return readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Asigna el usuario creador automáticamente"""
        if not change:  # Solo en creación
            obj.creado_por = request.user
        
        # Si se está anulando, asignar usuario anulador
        if obj.estado == 'anulado' and change:
            original = Remito.objects.get(pk=obj.pk)
            if original.estado != 'anulado':
                obj.anulado_por = request.user
        
        super().save_model(request, obj, form, change)


@admin.register(ItemRemito)
class ItemRemitoAdmin(admin.ModelAdmin):
    list_display = ('remito_nombre', 'descripcion_corta', 'cantidad', 'unidad_medida')
    list_filter = ('unidad_medida', 'remito__estado')
    search_fields = ('descripcion', 'codigo', 'remito__cliente__nombre')
    list_select_related = ('remito', 'remito__cliente')
    
    def remito_nombre(self, obj):
        """Muestra el número formateado del remito"""
        return obj.remito.numero_formateado if obj.remito else 'Sin remito'
    remito_nombre.short_description = 'Remito'
    remito_nombre.admin_order_field = 'remito__numero'
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'


@admin.register(RemitoAdjunto)
class RemitoAdjuntoAdmin(admin.ModelAdmin):
    list_display = ('nombre_original', 'remito_nombre', 'tipo_display', 'tamaño_formateado', 'subido_por_nombre', 'fecha_subida')
    list_filter = ('tipo', 'fecha_subida', 'remito__estado')
    search_fields = ('nombre_original', 'descripcion', 'remito__numero_formateado', 'remito__cliente__nombre')
    readonly_fields = ('tamaño', 'extension', 'nombre_original', 'subido_por', 'fecha_subida', 'fecha_modificacion', 'get_tamaño_formateado')
    
    def remito_nombre(self, obj):
        """Muestra el número formateado del remito"""
        return obj.remito.numero_formateado if obj.remito else 'Sin remito'
    remito_nombre.short_description = 'Remito'
    remito_nombre.admin_order_field = 'remito__numero'
    
    def tipo_display(self, obj):
        """Muestra el tipo con emoji"""
        tipo_map = {
            'entrega': '📦',
            'firma': '✍️',
            'foto': '🖼️',
            'documento': '📄',
            'otro': '📎'
        }
        emoji = tipo_map.get(obj.tipo, '📎')
        return f"{emoji} {obj.get_tipo_display()}"
    tipo_display.short_description = 'Tipo'
    
    def tamaño_formateado(self, obj):
        return obj.get_tamaño_formateado()
    tamaño_formateado.short_description = 'Tamaño'
    
    def subido_por_nombre(self, obj):
        """Muestra el nombre del usuario que subió el archivo"""
        if obj.subido_por:
            return f"{obj.subido_por.first_name} {obj.subido_por.last_name}".strip() or obj.subido_por.username
        return 'Desconocido'
    subido_por_nombre.short_description = 'Subido por'