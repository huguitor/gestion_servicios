from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CargoViewSet, EmpleadoViewSet, GrupoViewSet, RolPersonalViewSet, UsuarioInternoViewSet

router = DefaultRouter()
router.register("empleados", EmpleadoViewSet, basename="personal-empleados")
router.register("roles", RolPersonalViewSet, basename="personal-roles")
router.register("cargos", CargoViewSet, basename="personal-cargos")
router.register("usuarios", UsuarioInternoViewSet, basename="personal-usuarios")
router.register("grupos", GrupoViewSet, basename="personal-grupos")

urlpatterns = [path("", include(router.urls))]
