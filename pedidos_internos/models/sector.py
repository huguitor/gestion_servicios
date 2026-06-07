# gestion/backend/pedidos_internos/models/sector.py

from django.db import models


class Sector(models.Model):
    """
    Sector o área operativa de la empresa.

    Ejemplos: TALLER, COMPRAS, DEPOSITO_1, DEPOSITO_2, LOGISTICA.
    Un pedido interno nace en un sector_origen y se dirige a uno o
    varios sectores destino.
    """

    codigo = models.CharField(
        max_length=30,
        unique=True,
        help_text="Identificador corto, ej. TALLER, DEPOSITO_1."
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, default="")

    direccion = models.CharField(max_length=200, blank=True, default="")
    ciudad = models.CharField(max_length=100, blank=True, default="")
    provincia = models.CharField(max_length=100, blank=True, default="")

    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Sector"
        verbose_name_plural = "Sectores"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
