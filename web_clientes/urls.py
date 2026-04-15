# gestion_servicios/web_clientes/urls.py
from django.urls import path

from .views import (
    RegistroClienteWebView,
    LoginClienteWebView,
    MiPerfilView,
)

urlpatterns = [
    path("registro/", RegistroClienteWebView.as_view(), name="web-clientes-registro"),
    path("login/", LoginClienteWebView.as_view(), name="web-clientes-login"),
    path("mi-perfil/", MiPerfilView.as_view(), name="web-clientes-mi-perfil"),
]