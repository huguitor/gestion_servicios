# gestion/proveedores/models.py
from django.db import models
from django.core.validators import RegexValidator

class Proveedor(models.Model):
    TIPO_CHOICES = [
        ("fisica", "Persona Física"),
        ("juridica", "Persona Jurídica"),
    ]
    CONDICION_IVA_CHOICES = [
        ("ri", "Responsable Inscripto"),
        ("mono", "Monotributista"),
        ("exento", "Exento"),
        ("noresidente", "No Residente"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="juridica")
    nombre = models.CharField(max_length=200, help_text="Nombre o Razón Social")
    documento = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r'^\d{8,11}$', message="DNI/CUIT inválido")],
        help_text="DNI (8 dígitos) o CUIT (11 dígitos)"
    )
    condicion_iva = models.CharField(max_length=20, choices=CONDICION_IVA_CHOICES, default="ri")

    telefono = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    provincia = models.CharField(max_length=100, blank=True, null=True)
    pais = models.CharField(max_length=100, default="Argentina")

    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['documento'])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(documento__regex=r'^\d{8}$') | models.Q(documento__regex=r'^\d{11}$') | models.Q(documento__isnull=True),
                name='proveedor_valid_documento'
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.documento or 'sin CUIT'})"