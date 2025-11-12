# gestion/configuracion/fields.py
from django.db.models import ImageField
from django.db.models.fields.files import ImageFieldFile
from PIL import Image
import io
import os

class RedimensionableImageFieldFile(ImageFieldFile):
    def save(self, name, content, save=True):
        # Obtener la instancia del modelo para acceder a los campos de configuración
        if self.instance and self.instance.pk:
            # Procesar la imagen con las configuraciones del modelo
            content = self.redimensionar_imagen(content, self.instance)
        
        super().save(name, content, save)
    
    def redimensionar_imagen(self, content, instance):
        """Redimensiona la imagen según la configuración del modelo"""
        try:
            # Abrir imagen
            img = Image.open(content)
            
            # Convertir a RGB si es necesario (para JPEG)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Obtener configuración específica para este campo
            config = self.obtener_configuracion(instance, self.field.name)
            if not config:
                return content
            
            max_width = config['max_width']
            max_height = config['max_height']
            mantener_proporcion = config['mantener_proporcion']
            
            # Si no hay dimensiones definidas, retornar original
            if not max_width and not max_height:
                return content
            
            ancho_original, alto_original = img.size
            
            # Calcular nuevas dimensiones
            if mantener_proporcion:
                # Mantener relación de aspecto usando thumbnail
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            else:
                # Forzar dimensiones exactas (puede distorsionar)
                img = img.resize((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Guardar en buffer
            output = io.BytesIO()
            
            # Determinar formato basado en extensión original
            formato = 'JPEG'
            if hasattr(content, 'name'):
                nombre = content.name.lower()
                if nombre.endswith('.png'):
                    formato = 'PNG'
                elif nombre.endswith('.webp'):
                    formato = 'WEBP'
            
            if formato == 'PNG':
                img.save(output, format=formato, optimize=True)
            else:
                img.save(output, format=formato, quality=85, optimize=True)
            
            output.seek(0)
            return output
        
        except Exception as e:
            # Si hay error, retornar imagen original
            print(f"Error procesando imagen {self.field.name}: {e}")
        
        return content
    
    def obtener_configuracion(self, instance, field_name):
        """Obtiene la configuración de dimensiones para el campo específico"""
        config_map = {
            'logo_principal': {
                'ancho_field': 'logo_principal_ancho',
                'alto_field': 'logo_principal_alto', 
                'proporcion_field': 'logo_principal_proporcion'
            },
            'logo_favicon': {
                'ancho_field': 'logo_favicon_ancho',
                'alto_field': 'logo_favicon_alto',
                'proporcion_field': 'logo_favicon_proporcion'
            },
            'logo_tkinter': {
                'ancho_field': 'logo_tkinter_ancho',
                'alto_field': 'logo_tkinter_alto',
                'proporcion_field': 'logo_tkinter_proporcion'
            },
            'imagen_publicitaria_1': {
                'ancho_field': 'imagen_publicitaria_1_ancho',
                'alto_field': 'imagen_publicitaria_1_alto',
                'proporcion_field': 'imagen_publicitaria_1_proporcion'
            },
            'imagen_publicitaria_2': {
                'ancho_field': 'imagen_publicitaria_2_ancho',
                'alto_field': 'imagen_publicitaria_2_alto',
                'proporcion_field': 'imagen_publicitaria_2_proporcion'
            },
            'imagen_publicitaria_3': {
                'ancho_field': 'imagen_publicitaria_3_ancho',
                'alto_field': 'imagen_publicitaria_3_alto',
                'proporcion_field': 'imagen_publicitaria_3_proporcion'
            },
        }
        
        if field_name in config_map:
            config = config_map[field_name]
            return {
                'max_width': getattr(instance, config['ancho_field'], None),
                'max_height': getattr(instance, config['alto_field'], None),
                'mantener_proporcion': getattr(instance, config['proporcion_field'], True)
            }
        
        return None

class RedimensionableImageField(ImageField):
    attr_class = RedimensionableImageFieldFile
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)