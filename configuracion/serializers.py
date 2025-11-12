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
    
    class Meta:
        model = ConfiguracionGlobal
        fields = [
            # Datos básicos
            'id', 'nombre_empresa', 'cuit', 'direccion', 'telefono', 'email', 'pagina_web',
            
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
            'moneda', 'pais', 'idioma', 'activo', 'creado', 'actualizado'
        ]
        read_only_fields = [
            'id', 'creado', 'actualizado', 
            'logo_principal_url', 'logo_favicon_url', 'logo_tkinter_url',
            'imagen_publicitaria_1_url', 'imagen_publicitaria_2_url', 'imagen_publicitaria_3_url',
            'logo_principal_absolute_url', 'logo_favicon_absolute_url', 'logo_tkinter_absolute_url',
            'imagen_publicitaria_1_absolute_url', 'imagen_publicitaria_2_absolute_url', 'imagen_publicitaria_3_absolute_url'
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