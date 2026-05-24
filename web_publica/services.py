# gestion/backend/web_publica/services.py

from productos.models import Producto, Servicio
from configuracion.models import ConfiguracionGlobal


class WebPublicaService:

    @staticmethod
    def get_configuracion():
        return ConfiguracionGlobal.objects.filter(activo=True).first()

    @staticmethod
    def get_ofertas_home():
        """
        Ofertas públicas:
        - visibles sin login
        - muestran precio
        - funcionan como gancho comercial
        """
        return Producto.objects.filter(
            activo=True,
            publicado_web=True,
            destacado_web=True
        ).select_related("categoria", "marca").order_by("orden_web", "-id")

    @staticmethod
    def get_productos_seleccionados_home():
        """
        Productos seleccionados para portada:
        - visibles sin login
        - NO necesariamente muestran precio
        - sirven como vidriera comercial
        """
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
        ofertas = WebPublicaService.get_ofertas_home()
        productos_seleccionados = WebPublicaService.get_productos_seleccionados_home()
        servicios = WebPublicaService.get_servicios_home()

        return {
            "config": config,
            "ofertas": ofertas,
            "productos_seleccionados": productos_seleccionados,
            "servicios": servicios,
        }