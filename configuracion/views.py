# gestion/backend/configuracion/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny

from .models import ConfiguracionGlobal
from .serializers import ConfiguracionGlobalSerializer
from .services import ConfiguracionService
from licensing.manager import license_manager


class ConfiguracionGlobalViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionGlobal.objects.all()
    serializer_class = ConfiguracionGlobalSerializer
    permission_classes = [IsAdminUser]

    def get_serializer_context(self):
        """Incluir request en el contexto del serializer"""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        return ConfiguracionGlobal.objects.filter(activo=True)

    @action(detail=False, methods=["get"])
    def actual(self, request):
        """Obtener configuración activa actual"""
        config = ConfiguracionService.obtener_configuracion()
        serializer = self.get_serializer(config)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def datos_empresa(self, request):
        """Obtener solo datos de la empresa para otras apps"""
        datos = ConfiguracionService.obtener_datos_empresa()
        return Response(datos)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def config_login(self, request):
        """
        Configuración pública para login y frontends.

        IMPORTANTE:
        Solo devuelve información no sensible.

        Los módulos devueltos son módulos efectivos:
        .env AND license.json
        """

        config_data = ConfiguracionService.obtener_config_login()

        modulos = {
            # Módulos principales
            "clientes": license_manager.is_enabled("clientes"),
            "productos": license_manager.is_enabled("productos"),
            "presupuestos": license_manager.is_enabled("presupuestos"),
            "pedidos": license_manager.is_enabled("pedidos"),
            "remitos": license_manager.is_enabled("remitos"),
            "stock": license_manager.is_enabled("stock"),
            "backup": license_manager.is_enabled("backup"),
            "web_publica": license_manager.is_enabled("web_publica"),

            # Compatibilidad con portal/login actual
            "registro": license_manager.is_enabled("clientes"),
            "carrito": license_manager.is_enabled("pedidos"),
        }

        public_data = {
            "nombre_fantasia": config_data.get("nombre_fantasia"),
            "descripcion_sistema": config_data.get("descripcion_sistema"),
            "logo_url": config_data.get("logo_url"),
            "modulos": modulos,
        }

        if public_data.get("logo_url"):
            public_data["logo_absolute_url"] = public_data["logo_url"]
        else:
            public_data["logo_absolute_url"] = None

        print(f"🔐 Configuración login pública enviada: {public_data}")

        return Response(public_data)

    @action(detail=False, methods=["get"])
    def config_presupuestos(self, request):
        """Obtener configuración para presupuestos"""
        config = ConfiguracionService.obtener_config_presupuestos()
        return Response(config)

    @action(detail=True, methods=["post"])
    def reprocesar_imagen(self, request, pk=None):
        """Reprocesar una imagen específica"""
        config = self.get_object()
        campo_imagen = request.data.get("campo")

        campos_permitidos = [
            "logo_principal",
            "logo_favicon",
            "logo_tkinter",
            "imagen_publicitaria_1",
            "imagen_publicitaria_2",
            "imagen_publicitaria_3",
        ]

        if campo_imagen not in campos_permitidos:
            return Response(
                {
                    "error": (
                        "Campo no válido. Campos permitidos: "
                        f"{', '.join(campos_permitidos)}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            config.reprocesar_imagenes()
            return Response(
                {
                    "mensaje": (
                        f"Imagen {campo_imagen} "
                        "reprocesada correctamente"
                    )
                }
            )

        except Exception as e:
            return Response(
                {
                    "error": (
                        f"Error reprocesando imagen: {str(e)}"
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def estado_imagenes(self, request, pk=None):
        """Obtener estado actual de las imágenes vs configuración"""
        from .services import ProcesadorImagenes

        estado = ProcesadorImagenes.obtener_estado_imagenes()

        return Response(estado)