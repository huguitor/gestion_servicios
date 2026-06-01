# gestion/backend/configuracion/serializers.py

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
   
    # ⭐⭐ NOTA: Ya NO incluir estado_sincronizacion_numeracion
    # La numeración ahora se maneja exclusivamente desde Comprobante
    
    class Meta:
        model = ConfiguracionGlobal
        fields = [
            # 👇 Datos básicos de la empresa
            'id', 
            'nombre_empresa', 
            'nombre_fantasia', 
            'descripcion_sistema', 
            'cuit', 
            'direccion', 
            'telefono', 
            'email', 
            'pagina_web',
           
            # 👇 Campos de imágenes (archivos) - para edición en admin
            'logo_principal', 
            'logo_favicon', 
            'logo_tkinter',
            'imagen_publicitaria_1', 
            'imagen_publicitaria_2', 
            'imagen_publicitaria_3',
           
            # 👇 URLs relativas (solo lectura)
            'logo_principal_url', 
            'logo_favicon_url', 
            'logo_tkinter_url',
            'imagen_publicitaria_1_url', 
            'imagen_publicitaria_2_url', 
            'imagen_publicitaria_3_url',
           
            # 👇 URLs absolutas (solo lectura)
            'logo_principal_absolute_url', 
            'logo_favicon_absolute_url', 
            'logo_tkinter_absolute_url',
            'imagen_publicitaria_1_absolute_url', 
            'imagen_publicitaria_2_absolute_url', 
            'imagen_publicitaria_3_absolute_url',
           
            # 👇 Configuración de presupuestos (SIN NUMERACIÓN)
            'condiciones_comerciales', 
            'iva_por_defecto', 
            'dias_validez_presupuesto',
            
            # ⭐⭐ IMPORTANTE: Ya NO incluir 'proximo_numero_presupuesto'
            # La numeración se maneja exclusivamente desde comprobantes/models.py
           
            # 👇 Configuración general
            'moneda', 
            'pais', 
            'idioma', 
            'activo', 
            'creado', 
            'actualizado',
           
            # ⭐⭐ NOTA: Ya NO incluir 'estado_sincronizacion_numeracion'
        ]
        read_only_fields = [
            # Campos generados automáticamente
            'id', 
            'creado', 
            'actualizado',
            
            # URLs de imágenes (solo lectura)
            'logo_principal_url', 
            'logo_favicon_url', 
            'logo_tkinter_url',
            'imagen_publicitaria_1_url', 
            'imagen_publicitaria_2_url', 
            'imagen_publicitaria_3_url',
            'logo_principal_absolute_url', 
            'logo_favicon_absolute_url', 
            'logo_tkinter_absolute_url',
            'imagen_publicitaria_1_absolute_url', 
            'imagen_publicitaria_2_absolute_url', 
            'imagen_publicitaria_3_absolute_url',
        ]
   
    # 👇 Métodos para obtener URLs seguras
    def _safe_file_url(self, obj, field_name):
        archivo = getattr(obj, field_name, None)

        if archivo and hasattr(archivo, "url"):
            try:
                return archivo.url
            except ValueError:
                return None

        return None

    def _safe_absolute_file_url(self, obj, field_name):
        url = self._safe_file_url(obj, field_name)

        if not url:
            return None

        request = self.context.get("request")

        if request is not None:
            return request.build_absolute_uri(url)

        return url

    def get_logo_principal_url(self, obj):
        return self._safe_file_url(obj, "logo_principal")
   
    def get_logo_favicon_url(self, obj):
        return self._safe_file_url(obj, "logo_favicon")
   
    def get_logo_tkinter_url(self, obj):
        return self._safe_file_url(obj, "logo_tkinter")
   
    def get_imagen_publicitaria_1_url(self, obj):
        return self._safe_file_url(obj, "imagen_publicitaria_1")
   
    def get_imagen_publicitaria_2_url(self, obj):
        return self._safe_file_url(obj, "imagen_publicitaria_2")
   
    def get_imagen_publicitaria_3_url(self, obj):
        return self._safe_file_url(obj, "imagen_publicitaria_3")

    def get_logo_principal_absolute_url(self, obj):
        return self._safe_absolute_file_url(obj, "logo_principal")
   
    def get_logo_favicon_absolute_url(self, obj):
        return self._safe_absolute_file_url(obj, "logo_favicon")
   
    def get_logo_tkinter_absolute_url(self, obj):
        return self._safe_absolute_file_url(obj, "logo_tkinter")
   
    def get_imagen_publicitaria_1_absolute_url(self, obj):
        return self._safe_absolute_file_url(obj, "imagen_publicitaria_1")
   
    def get_imagen_publicitaria_2_absolute_url(self, obj):
        return self._safe_absolute_file_url(obj, "imagen_publicitaria_2")
   
    def get_imagen_publicitaria_3_absolute_url(self, obj):
        return self._safe_absolute_file_url(obj, "imagen_publicitaria_3")
   
    # ⭐⭐ NOTA: Ya NO existe el método get_estado_sincronizacion_numeracion()
    # La numeración ahora se maneja exclusivamente desde Comprobante
   
    def validate(self, data):
        """Validación general de la configuración"""
        # Validar que el IVA sea positivo
        if 'iva_por_defecto' in data and data['iva_por_defecto'] < 0:
            raise serializers.ValidationError({
                'iva_por_defecto': 'El IVA no puede ser negativo'
            })
        
        # Validar que los días de validez sean positivos
        if 'dias_validez_presupuesto' in data and data['dias_validez_presupuesto'] <= 0:
            raise serializers.ValidationError({
                'dias_validez_presupuesto': 'Los días de validez deben ser mayores a 0'
            })
        
        return data
   
    def create(self, validated_data):
        """Crear nueva configuración global"""
        # ⭐⭐ IMPORTANTE: Solo una configuración activa
        # Si ya hay una configuración activa, desactivarla
        ConfiguracionGlobal.objects.filter(activo=True).update(activo=False)
       
        # Crear la nueva configuración
        config = super().create(validated_data)
       
        # ⭐⭐ NOTA: Ya no hay sincronización con Comprobante
        # La numeración se maneja exclusivamente desde comprobantes/models.py
       
        print(f"✅ Configuración creada: {config.nombre_empresa} (ID: {config.id})")
        return config
   
    def update(self, instance, validated_data):
        """Actualizar configuración existente"""
        # Si esta configuración se va a activar, desactivar las demás
        if validated_data.get('activo', instance.activo):
            ConfiguracionGlobal.objects.exclude(pk=instance.pk).update(activo=False)
       
        # Actualizar la instancia
        instance = super().update(instance, validated_data)
       
        # ⭐⭐ NOTA: Ya no hay sincronización con Comprobante
        # La numeración se maneja exclusivamente desde comprobantes/models.py
       
        print(f"✅ Configuración actualizada: {instance.nombre_empresa} (ID: {instance.id})")
        return instance