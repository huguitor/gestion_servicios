# gestion/comprobantes/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP

class Comprobante(models.Model):
    TIPO_COMPROBANTE = [
        ("PRES", "Presupuesto"),  # Solo "Presupuesto" por ahora, expandable luego
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_COMPROBANTE, default="PRES")
    serie = models.CharField(max_length=5, default="00001")   # Punto de venta
    numero = models.IntegerField(editable=False)  # Correlativo automático
    numero_inicial = models.IntegerField(default=1)  # Número autorizado inicial
    numero_final = models.IntegerField()  # Número autorizado final
    numero_comienzo = models.IntegerField()  # Punto de inicio de la secuencia

    class Meta:
        unique_together = ('tipo', 'serie', 'numero')
        indexes = [models.Index(fields=['tipo', 'serie', 'numero'])] 

    def save(self, *args, **kwargs):
        if not self.numero:
            # Obtener el último número para el tipo y serie actuales
            last_numero = Comprobante.objects.filter(
                tipo=self.tipo, serie=self.serie
            ).aggregate(models.Max('numero'))['numero__max'] or 0

            # Calcular el siguiente número, empezando desde numero_comienzo
            if last_numero < self.numero_comienzo:
                self.numero = self.numero_comienzo
            else:
                self.numero = last_numero + 1

            # Validar que no exceda el rango
            if self.numero > self.numero_final:
                raise ValidationError(f"El número {self.numero} excede el rango máximo {self.numero_final}.")
            if self.numero < self.numero_inicial:
                raise ValidationError(f"El número {self.numero} es menor al rango inicial {self.numero_inicial}.")

        # Validar que numero_comienzo esté dentro del rango
        if self.numero_comienzo < self.numero_inicial or self.numero_comienzo > self.numero_final:
            raise ValidationError("El numero_comienzo debe estar dentro del rango de numero_inicial y numero_final.")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tipo} {self.serie}-{self.numero:06d}"  # Formato con 6 dígitos (e.g., 000020)