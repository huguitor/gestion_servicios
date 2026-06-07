# gestion/backend/pedidos_internos/models/usuario_sector.py

from django.conf import settings
from django.db import models

from .sector import Sector


class UsuarioSector(models.Model):
    """
    Vínculo entre un usuario y un sector.

    Un usuario puede pertenecer a varios sectores (ej. trabaja en
    COMPRAS pero también cubre DEPOSITO_1). `principal` marca el
    sector por defecto del usuario.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sectores",
    )

    sector = models.ForeignKey(
        Sector,
        on_delete=models.CASCADE,
        related_name="usuarios",
    )

    principal = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "sector")
        verbose_name = "Usuario por sector"
        verbose_name_plural = "Usuarios por sector"
        ordering = ["sector", "usuario"]

    def __str__(self):
        return f"{self.usuario} @ {self.sector.codigo}"
