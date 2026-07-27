from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class RolPersonal(models.Model):
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, default="")
    grupo = models.OneToOneField(
        Group,
        on_delete=models.PROTECT,
        related_name="rol_personal",
    )
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "Rol de personal"
        verbose_name_plural = "Roles de personal"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Cargo(models.Model):
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="empleado",
    )
    legajo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    documento = models.CharField(max_length=30, unique=True, null=True, blank=True)
    fecha_ingreso = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    rol = models.ForeignKey(
        RolPersonal,
        on_delete=models.PROTECT,
        related_name="empleados",
        null=True,
        blank=True,
    )
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        related_name="empleados",
        null=True,
        blank=True,
    )
    observaciones = models.TextField(blank=True, default="")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["usuario__last_name", "usuario__first_name", "usuario__username"]
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        permissions = [
            ("access_admin_frontend", "Puede acceder al frontend administrativo"),
        ]

    def save(self, *args, **kwargs):
        self.legajo = self.legajo.strip() if self.legajo else None
        self.documento = self.documento.strip() if self.documento else None
        super().save(*args, **kwargs)

    def __str__(self):
        nombre = self.usuario.get_full_name().strip()
        identificador = nombre or self.usuario.get_username()
        return f"{self.legajo} - {identificador}" if self.legajo else identificador
