from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from pedidos_internos.models import UsuarioSector
from personal.models import Cargo, Empleado, RolPersonal
from personal.permissions import PuedeGestionarPersonal
from .serializers import CargoSerializer, EmpleadoSerializer, GrupoSerializer, RolPersonalSerializer, UsuarioInternoSerializer


class BasePersonalViewSet(viewsets.ModelViewSet):
    permission_classes = [PuedeGestionarPersonal]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


class EmpleadoViewSet(BasePersonalViewSet):
    queryset = Empleado.objects.select_related("usuario", "rol__grupo", "cargo").all()
    serializer_class = EmpleadoSerializer
    search_fields = ["usuario__username", "usuario__first_name", "usuario__last_name", "usuario__email", "legajo", "documento"]
    ordering_fields = ["legajo", "usuario__username", "activo", "creado"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        filtro = self.request.query_params.get("informe")
        if filtro == "sin_sector":
            queryset = queryset.exclude(usuario_id__in=UsuarioSector.objects.filter(activo=True, sector__activo=True).values("usuario_id"))
        elif filtro == "administrativos_sin_sector":
            queryset = queryset.filter(
                Q(usuario__user_permissions__codename="access_admin_frontend")
                | Q(usuario__groups__permissions__codename="access_admin_frontend")
                | Q(usuario__is_superuser=True)
            ).exclude(usuario_id__in=UsuarioSector.objects.filter(activo=True, sector__activo=True).values("usuario_id"))
        elif filtro == "sin_rol":
            queryset = queryset.filter(rol__isnull=True)
        return queryset.distinct()

    @action(detail=True, methods=["post"])
    def activar(self, request, pk=None):
        empleado = self.get_object()
        empleado.activo = True
        empleado.save(update_fields=["activo", "actualizado"])
        return Response(self.get_serializer(empleado).data)

    @action(detail=True, methods=["post"])
    def desactivar(self, request, pk=None):
        empleado = self.get_object()
        empleado.activo = False
        empleado.save(update_fields=["activo", "actualizado"])
        return Response(self.get_serializer(empleado).data)


class RolPersonalViewSet(BasePersonalViewSet):
    queryset = RolPersonal.objects.select_related("grupo").all()
    serializer_class = RolPersonalSerializer
    search_fields = ["codigo", "nombre", "descripcion", "grupo__name"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]


class CargoViewSet(BasePersonalViewSet):
    queryset = Cargo.objects.all()
    serializer_class = CargoSerializer
    search_fields = ["codigo", "nombre", "descripcion"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]


class UsuarioInternoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UsuarioInternoSerializer
    permission_classes = [PuedeGestionarPersonal]
    required_permission = "personal.view_empleado"
    queryset = get_user_model().objects.filter(cliente_web__isnull=True).order_by("username")

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("sin_empleado"):
            queryset = queryset.filter(empleado__isnull=True)
        if self.request.query_params.get("con_sector_sin_empleado"):
            queryset = queryset.filter(empleado__isnull=True, id__in=UsuarioSector.objects.values("usuario_id"))
        return queryset.distinct()


class GrupoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all().order_by("name")
    serializer_class = GrupoSerializer
    permission_classes = [PuedeGestionarPersonal]
    required_permission = "personal.view_rolpersonal"
