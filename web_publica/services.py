# gestion/web_publica/services.py

from productos.models import Producto, Servicio
from configuracion.models import ConfiguracionGlobal


class WebPublicaService:

    @staticmethod
    def get_configuracion():
        return ConfiguracionGlobal.objects.filter(activo=True).first()

    @staticmethod
    def get_productos_home():
        return Producto.objects.filter(
            activo=True,
            publicado_web=True,
            mostrar_en_home=True
        ).select_related("categoria", "marca").order_by("orden_web", "-id")

    @staticmethod
    def get_servicios_home():
        return Servicio.objects.filter(
            activo=True,
            publicado_web=True,
            mostrar_en_home=True
        ).select_related("categoria", "marca").order_by("orden_web", "-id")

    @staticmethod
    def get_home_data():
        config = WebPublicaService.get_configuracion()
        productos = WebPublicaService.get_productos_home()
        servicios = WebPublicaService.get_servicios_home()

        return {
            "config": config,
            "productos": productos,
            "servicios": servicios,
        }