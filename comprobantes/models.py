# gestion/comprobantes/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP


class Comprobante(models.Model):
    TIPO_COMPROBANTE = [
        ("PRES", "Presupuesto"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_COMPROBANTE, default="PRES")
    serie = models.CharField(max_length=5, default="00001")
    numero = models.IntegerField(editable=False)  # ID interno del comprobante
    
    # ⭐ CAMPOS EXISTENTES (MANTENER)
    numero_inicial = models.IntegerField(
        default=1,
        help_text="Primer número autorizado del rango (ej: 1)"
    )
    numero_final = models.IntegerField(
        default=500,
        help_text="Último número autorizado actualmente (ej: 500)"
    )
    
    # ⭐⭐ CAMBIO CLAVE: numero_comienzo → proximo_numero
    # numero_comienzo = models.IntegerField()  # ← VIEJO NOMBRE
    proximo_numero = models.IntegerField(
        default=1,
        help_text="Próximo número que se usará realmente. Ejemplo: Si el último presupuesto fue #49, aquí debe ir 50"
    )

    class Meta:
        unique_together = ('tipo', 'serie', 'numero')
        indexes = [models.Index(fields=['tipo', 'serie', 'numero'])]

    def save(self, *args, **kwargs):
        if not self.numero:
            # Obtener el último número para el tipo y serie actuales
            last_numero = Comprobante.objects.filter(
                tipo=self.tipo, serie=self.serie
            ).aggregate(models.Max('numero'))['numero__max'] or 0
            self.numero = last_numero + 1

        # ⭐⭐ VALIDACIONES NUEVAS Y MEJORADAS
        if self.numero_inicial > self.numero_final:
            raise ValidationError(
                f"❌ El número inicial ({self.numero_inicial}) no puede ser mayor al final ({self.numero_final})."
            )
        
        if self.proximo_numero < self.numero_inicial:
            raise ValidationError(
                f"❌ El próximo número ({self.proximo_numero}) no puede ser menor al inicio ({self.numero_inicial}). "
                f"Configúralo igual o mayor."
            )
        
        if self.proximo_numero > self.numero_final:
            raise ValidationError(
                f"❌ El próximo número ({self.proximo_numero}) excede el límite actual ({self.numero_final}). "
                f"Amplía el rango primero o ajusta el próximo número."
            )

        super().save(*args, **kwargs)

    # ⭐⭐ PROPIEDADES CALCULADAS NUEVAS
    @property
    def numeros_disponibles(self):
        """Calcula cuántos números quedan disponibles"""
        if self.proximo_numero > self.numero_final:
            return 0
        disponibles = self.numero_final - self.proximo_numero + 1
        return max(0, disponibles)  # Nunca negativo
    
    @property
    def rango_disponible(self):
        """Devuelve el rango de números disponibles"""
        if self.proximo_numero > self.numero_final:
            return "❌ SIN NÚMEROS DISPONIBLES"
        return f"✅ {self.proximo_numero} - {self.numero_final}"
    
    @property
    def porcentaje_usado(self):
        """Porcentaje de números usados"""
        total_numeros = self.numero_final - self.numero_inicial + 1
        if total_numeros == 0:
            return 0
        numeros_usados = self.proximo_numero - self.numero_inicial
        porcentaje = (numeros_usados / total_numeros) * 100
        return round(porcentaje, 1)
    
    @property
    def estado_disponibilidad(self):
        """Estado visual de disponibilidad"""
        disponibles = self.numeros_disponibles
        if disponibles == 0:
            return ("❌ CRÍTICO", "red")
        elif disponibles <= 10:
            return ("⚠️ BAJO", "orange")
        elif disponibles <= 50:
            return ("⚠️ MEDIO", "yellow")
        else:
            return ("✅ NORMAL", "green")

    def __str__(self):
        return f"{self.tipo} {self.serie}-{self.numero:06d}"
    
    def info_para_admin(self):
        """Información detallada para el admin"""
        estado, color = self.estado_disponibilidad
        return (
            f"{self.tipo} {self.serie} | "
            f"Próximo: {self.proximo_numero} | "
            f"Disponibles: {self.numeros_disponibles} | "
            f"Estado: {estado}"
        )