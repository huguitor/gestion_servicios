# gestion/backend/web_clientes/urls.py
from django.urls import path

from .views import (
    RegistroClienteWebView,
    LoginClienteWebView,
    GoogleLoginClienteWebView,
    MiPerfilView,
    VerificarEmailClienteWebView,
    ReenviarVerificacionEmailView,
)

urlpatterns = [
    path("registro/", RegistroClienteWebView.as_view(), name="web-clientes-registro"),
    path("login/", LoginClienteWebView.as_view(), name="web-clientes-login"),
    path("google-login/", GoogleLoginClienteWebView.as_view(), name="web-clientes-google-login"),
    path("mi-perfil/", MiPerfilView.as_view(), name="web-clientes-mi-perfil"),
    path("verificar-email/<path:token>/", VerificarEmailClienteWebView.as_view(), name="web-clientes-verificar-email"),
    path("reenviar-verificacion-email/", ReenviarVerificacionEmailView.as_view(), name="web-clientes-reenviar-verificacion-email"),
]