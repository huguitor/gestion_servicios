# gestion_servicios/web_clientes/models.py
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class ClienteWeb(models.Model):
    """
    Perfil web del cliente.
    Usa auth.User para login/autenticación
    y se vincula opcionalmente con clientes.Cliente
    para integrarse con el sistema comercial interno.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cliente_web"
    )

    cliente = models.OneToOneField(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfil_web",
        help_text="Cliente comercial vinculado, si existe."
    )

    telefono = models.CharField(
        max_length=30,
        blank=True,
        default=""
    )

    activo = models.BooleanField(default=True)

    email_verificado = models.BooleanField(
        default=False,
        help_text="Indica si el email fue verificado."
    )

    acepta_terminos = models.BooleanField(
        default=False,
        help_text="Aceptación de términos y condiciones."
    )

    fecha_alta = models.DateTimeField(auto_now_add=True)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Cliente web"
        verbose_name_plural = "Clientes web"

    def __str__(self):
        nombre = self.user.get_full_name().strip()
        if nombre:
            return f"{nombre} ({self.user.email})"
        return self.user.username

    def clean(self):
        if not self.user.email:
            raise ValidationError("El usuario web debe tener email.")