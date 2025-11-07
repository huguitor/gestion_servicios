# gestion/impuestos/models.py
from django.db import models
from django.core.validators import MinValueValidator

class Impuesto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)]
    )
    tipo = models.CharField(
        max_length=20,
        choices=[("compra", "Compra"), ("venta", "Venta"), ("ambos", "Ambos")],
        default="ambos"
    )
    # 👇 AGREGAR ESTOS CAMPOS FALTANTES
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['nombre'])]

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje}%)"


