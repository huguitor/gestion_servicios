# gestion/comprobantes/models.py
from django.db import models
from django.core.exceptions import ValidationError


class Comprobante(models.Model):
    TIPO_COMPROBANTE = [
        ("PRES", "Presupuesto"),
        ("REMI", "Remito Interno"),  # ⭐ AGREGADO
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_COMPROBANTE, default="PRES")
    serie = models.CharField(max_length=5, default="00001")
    numero = models.IntegerField(editable=False)
    
    # ⭐ CAMBIO: numero_comienzo → proximo_numero
    numero_inicial = models.IntegerField(default=1)
    numero_final = models.IntegerField()
    proximo_numero = models.IntegerField(default=1)  # ⭐ CON DEFAULT=1

    class Meta:
        unique_together = ('tipo', 'serie', 'numero')
        indexes = [models.Index(fields=['tipo', 'serie', 'numero'])]

    def save(self, *args, **kwargs):
        if not self.numero:
            last_numero = Comprobante.objects.filter(
                tipo=self.tipo, serie=self.serie
            ).aggregate(models.Max('numero'))['numero__max'] or 0

            # ⭐ CAMBIADO: numero_comienzo → proximo_numero
            if last_numero < self.proximo_numero:
                self.numero = self.proximo_numero
            else:
                self.numero = last_numero + 1

            # Validar que no exceda el rango
            if self.numero > self.numero_final:
                raise ValidationError(f"El número {self.numero} excede el rango máximo {self.numero_final}.")
            if self.numero < self.numero_inicial:
                raise ValidationError(f"El número {self.numero} es menor al rango inicial {self.numero_inicial}.")

        # ⭐ CAMBIADO: numero_comienzo → proximo_numero
        if self.proximo_numero < self.numero_inicial or self.proximo_numero > self.numero_final:
            raise ValidationError("El proximo_numero debe estar dentro del rango de numero_inicial y numero_final.")

        super().save(*args, **kwargs)
    
    # ⭐ NUEVAS PROPIEDADES
    @property
    def numeros_disponibles(self):
        """Cuántos números quedan disponibles"""
        if self.proximo_numero > self.numero_final:
            return 0
        return self.numero_final - self.proximo_numero + 1
    
    @property
    def porcentaje_usado(self):
        """Porcentaje de números usados"""
        total = self.numero_final - self.numero_inicial + 1
        if total == 0:
            return 0
        usados = self.proximo_numero - self.numero_inicial
        return round((usados / total) * 100, 1)

    def __str__(self):
        return f"{self.tipo} {self.serie}-{self.numero:06d}"