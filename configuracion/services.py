# gestion/configuracion/services.py
from .models import ConfiguracionGlobal
import os

class ConfiguracionService:
    """Servicio para acceder a la configuración desde cualquier app"""
    
    @staticmethod
    def obtener_configuracion():
        """Obtener la configuración activa actual"""
        config = ConfiguracionGlobal.objects.filter(activo=True).first()
        if not config:
            # Crear configuración por defecto si no existe
            config = ConfiguracionGlobal.objects.create(
                nombre_empresa="Mi Empresa S.A."
            )
        return config
    
    @staticmethod
    def obtener_datos_empresa():
        """Obtener datos de la empresa para documentos"""
        config = ConfiguracionService.obtener_configuracion()
        return {
            'nombre_empresa': config.nombre_empresa,
            'cuit': config.cuit,
            'direccion': config.direccion,
            'telefono': config.telefono,
            'email': config.email,
            'pagina_web': config.pagina_web,
            'logo_principal_url': config.logo_principal_url,
        }
    
    @staticmethod
    def obtener_logos_para_pdf():
        """Obtener todas las imágenes para PDFs"""
        config = ConfiguracionService.obtener_configuracion()
        return {
            'logo_principal': config.logo_principal_url,  # Para encabezado
            'imagenes_publicitarias': [
                config.imagen_publicitaria_1_url,
                config.imagen_publicitaria_2_url, 
                config.imagen_publicitaria_3_url,
            ]
        }
    
    @staticmethod
    def obtener_logo_tkinter():
        """Obtener logo específico para Tkinter"""
        config = ConfiguracionService.obtener_configuracion()
        return config.logo_tkinter_url
    
    @staticmethod
    def obtener_favicon():
        """Obtener favicon para la aplicación web"""
        config = ConfiguracionService.obtener_configuracion()
        return config.logo_favicon_url
    
    @staticmethod
    def obtener_config_presupuestos():
        """Obtener configuración específica para presupuestos"""
        config = ConfiguracionService.obtener_configuracion()
        return {
            'condiciones_comerciales': config.condiciones_comerciales,
            'iva_por_defecto': float(config.iva_por_defecto),
            'dias_validez': config.dias_validez_presupuesto,
        }
    
class ProcesadorImagenes:
    """Servicio para procesamiento de imágenes"""
    
    @staticmethod
    def reprocesar_todas_imagenes():
        """Reprocesa todas las imágenes del sistema con la configuración actual"""
        from .models import ConfiguracionGlobal
        
        config = ConfiguracionGlobal.objects.filter(activo=True).first()
        if config:
            config.reprocesar_imagenes()
            return True
        return False
    
    @staticmethod
    def obtener_estado_imagenes():
        """Obtiene información del estado actual de las imágenes"""
        from .models import ConfiguracionGlobal
        
        config = ConfiguracionGlobal.objects.filter(activo=True).first()
        if not config:
            return {}
        
        info = {}
        campos_imagen = [
            'logo_principal', 'logo_favicon', 'logo_tkinter',
            'imagen_publicitaria_1', 'imagen_publicitaria_2', 'imagen_publicitaria_3'
        ]
        
        for campo in campos_imagen:
            imagen_field = getattr(config, campo)
            if imagen_field and hasattr(imagen_field, 'path'):
                try:
                    from PIL import Image
                    with Image.open(imagen_field.path) as img:
                        info[campo] = {
                            'ancho_actual': img.width,
                            'alto_actual': img.height,
                            'config_ancho': getattr(config, f'{campo}_ancho'),
                            'config_alto': getattr(config, f'{campo}_alto'),
                            'tamaño_kb': os.path.getsize(imagen_field.path) / 1024,
                            'ruta': imagen_field.path
                        }
                except Exception as e:
                    info[campo] = {'error': str(e)}
            else:
                info[campo] = 'No disponible'
        
        return info