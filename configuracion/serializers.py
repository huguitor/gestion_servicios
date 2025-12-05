# gestion/configuracion/serializers.py
from rest_framework import serializers
from .models import ConfiguracionGlobal

class ConfiguracionGlobalSerializer(serializers.ModelSerializer):
    # 👇 URLs de todas las imágenes
    logo_principal_url = serializers.SerializerMethodField()
    logo_favicon_url = serializers.SerializerMethodField()
    logo_tkinter_url = serializers.SerializerMethodField()
    imagen_publicitaria_1_url = serializers.SerializerMethodField()
    imagen_publicitaria_2_url = serializers.SerializerMethodField()
    imagen_publicitaria_3_url = serializers.SerializerMethodField()
    
    # 👇 URLs absolutas (con dominio completo)
    logo_principal_absolute_url = serializers.SerializerMethodField()
    logo_favicon_absolute_url = serializers.SerializerMethodField()
    logo_tkinter_absolute_url = serializers.SerializerMethodField()
    imagen_publicitaria_1_absolute_url = serializers.SerializerMethodField()
    imagen_publicitaria_2_absolute_url = serializers.SerializerMethodField()
    imagen_publicitaria_3_absolute_url = serializers.SerializerMethodField()
    
    # ⭐⭐ NUEVO: Estado de sincronización de numeración
    estado_sincronizacion_numeracion = serializers.SerializerMethodField()
    
    class Meta:
        model = ConfiguracionGlobal
        fields = [
            # Datos básicos
            'id', 'nombre_empresa', 'nombre_fantasia', 'descripcion_sistema', 'cuit', 'direccion', 'telefono', 'email', 'pagina_web',
            
            # Campos de imágenes (archivos)
            'logo_principal', 'logo_favicon', 'logo_tkinter',
            'imagen_publicitaria_1', 'imagen_publicitaria_2', 'imagen_publicitaria_3',
            
            # URLs relativas
            'logo_principal_url', 'logo_favicon_url', 'logo_tkinter_url',
            'imagen_publicitaria_1_url', 'imagen_publicitaria_2_url', 'imagen_publicitaria_3_url',
            
            # URLs absolutas
            'logo_principal_absolute_url', 'logo_favicon_absolute_url', 'logo_tkinter_absolute_url',
            'imagen_publicitaria_1_absolute_url', 'imagen_publicitaria_2_absolute_url', 'imagen_publicitaria_3_absolute_url',
            
            # Configuración
            'condiciones_comerciales', 'iva_por_defecto', 'dias_validez_presupuesto',
            # ⭐⭐ NUEVO: Próximo número de presupuesto
            'proximo_numero_presupuesto',
            'moneda', 'pais', 'idioma', 'activo', 'creado', 'actualizado',
            
            # ⭐⭐ NUEVO: Estado de sincronización
            'estado_sincronizacion_numeracion'
        ]
        read_only_fields = [
            'id', 'creado', 'actualizado', 
            'logo_principal_url', 'logo_favicon_url', 'logo_tkinter_url',
            'imagen_publicitaria_1_url', 'imagen_publicitaria_2_url', 'imagen_publicitaria_3_url',
            'logo_principal_absolute_url', 'logo_favicon_absolute_url', 'logo_tkinter_absolute_url',
            'imagen_publicitaria_1_absolute_url', 'imagen_publicitaria_2_absolute_url', 'imagen_publicitaria_3_absolute_url',
            # ⭐⭐ NUEVO: Estado de sincronización es solo lectura
            'estado_sincronizacion_numeracion'
        ]
    
    # 👇 Métodos para URLs relativas
    def get_logo_principal_url(self, obj):
        return obj.logo_principal_url
    
    def get_logo_favicon_url(self, obj):
        return obj.logo_favicon_url
    
    def get_logo_tkinter_url(self, obj):
        return obj.logo_tkinter_url
    
    def get_imagen_publicitaria_1_url(self, obj):
        return obj.imagen_publicitaria_1_url
    
    def get_imagen_publicitaria_2_url(self, obj):
        return obj.imagen_publicitaria_2_url
    
    def get_imagen_publicitaria_3_url(self, obj):
        return obj.imagen_publicitaria_3_url
    
    # 👇 Métodos para URLs absolutas
    def get_logo_principal_absolute_url(self, obj):
        request = self.context.get('request')
        absolute_urls = obj.get_absolute_url(request)
        return absolute_urls.get('logo_principal')
    
    def get_logo_favicon_absolute_url(self, obj):
        request = self.context.get('request')
        absolute_urls = obj.get_absolute_url(request)
        return absolute_urls.get('logo_favicon')
    
    def get_logo_tkinter_absolute_url(self, obj):
        request = self.context.get('request')
        absolute_urls = obj.get_absolute_url(request)
        return absolute_urls.get('logo_tkinter')
    
    def get_imagen_publicitaria_1_absolute_url(self, obj):
        request = self.context.get('request')
        absolute_urls = obj.get_absolute_url(request)
        return absolute_urls.get('imagen_publicitaria_1')
    
    def get_imagen_publicitaria_2_absolute_url(self, obj):
        request = self.context.get('request')
        absolute_urls = obj.get_absolute_url(request)
        return absolute_urls.get('imagen_publicitaria_2')
    
    def get_imagen_publicitaria_3_absolute_url(self, obj):
        request = self.context.get('request')
        absolute_urls = obj.get_absolute_url(request)
        return absolute_urls.get('imagen_publicitaria_3')
    
    # ⭐⭐ NUEVO MÉTODO: Estado de sincronización
    def get_estado_sincronizacion_numeracion(self, obj):
        """Obtiene el estado de sincronización con Comprobante"""
        return obj.estado_sincronizacion_numeracion()
    
    def validate_proximo_numero_presupuesto(self, value):
        """Validar que el próximo número sea válido"""
        if value <= 0:
            raise serializers.ValidationError("El próximo número debe ser mayor a 0")
        
        if value > 999999:
            raise serializers.ValidationError("El próximo número es demasiado grande")
        
        return value
    
    def create(self, validated_data):
        """Crear nueva configuración"""
        # Si ya hay una configuración activa, desactivarla
        ConfiguracionGlobal.objects.filter(activo=True).update(activo=False)
        
        # Crear la nueva configuración
        config = super().create(validated_data)
        
        # Sincronizar con comprobante
        if hasattr(config, 'sincronizar_con_comprobante'):
            config.sincronizar_con_comprobante()
        
        return config
    
    def update(self, instance, validated_data):
        """Actualizar configuración existente"""
        # Actualizar instancia
        instance = super().update(instance, validated_data)
        
        # Si la configuración está activa, desactivar las demás
        if instance.activo:
            ConfiguracionGlobal.objects.exclude(pk=instance.pk).update(activo=False)
        
        # Sincronizar con comprobante si se cambió el próximo número
        if 'proximo_numero_presupuesto' in validated_data:
            instance.sincronizar_con_comprobante()
        
        return instance