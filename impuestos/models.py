# gestion/impuestos/models.py
from django.db import models
from django.core.validators import MinValueValidator


class Impuesto(models.Model):
    TIPO_CHOICES = [
        ("compra", "Compra"),
        ("venta", "Venta"), 
        ("ambos", "Ambos")
    ]
    
    nombre = models.CharField(max_length=100, unique=True)
    porcentaje = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0)]
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="ambos"
    )
    # Campo opcional para nombre display - Asegúrate que sea blank=True
    display_name = models.CharField(max_length=150, blank=True, null=True)  # ¡Importante: blank=True!
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['nombre'])]
        verbose_name_plural = "Impuestos"
        ordering = ['nombre']

    def save(self, *args, **kwargs):
        # Si display_name está vacío o solo tiene espacios
        if not self.display_name or self.display_name.strip() == '':
            # Generarlo automáticamente
            self.display_name = f"{self.nombre} ({self.porcentaje}%)"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or f"{self.nombre} ({self.porcentaje}%)"
