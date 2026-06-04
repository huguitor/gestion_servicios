# gestion/backend/archivos/models.py

import os

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


def archivo_upload_path(instance, filename):
    """
    Define la ubicación física del archivo.

    Ejemplos:

    media/archivos/imagen-producto-principal/foto1.jpg
    media/archivos/manual/manual_motor.pdf
    media/archivos/plano-cad/plano_v2.dwg
    """

    carpeta = "otros"

    if (
        instance.tipo
        and instance.tipo.carpeta
    ):
        carpeta = instance.tipo.carpeta

    return f"archivos/{carpeta}/{filename}"


class TipoArchivo(models.Model):
    """
    Tipos configurables de archivos.
    """

    nombre = models.CharField(
        max_length=100,
        unique=True
    )

    carpeta = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        help_text=(
            "Carpeta física donde se almacenarán "
            "los archivos de este tipo."
        )
    )

    descripcion = models.TextField(
        blank=True,
        null=True
    )

    icono = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    activo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Tipo de Archivo"
        verbose_name_plural = "Tipos de Archivos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):

        if not self.carpeta:
            self.carpeta = slugify(
                self.nombre
            )

        super().save(*args, **kwargs)


class Archivo(models.Model):
    """
    Repositorio central de archivos.
    """

    nombre = models.CharField(
        max_length=255
    )

    nombre_original = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    descripcion = models.TextField(
        blank=True,
        null=True
    )

    archivo = models.FileField(
        upload_to=archivo_upload_path
    )

    thumbnail = models.ImageField(
        upload_to="archivos/thumbnails/",
        blank=True,
        null=True
    )

    tipo = models.ForeignKey(
        TipoArchivo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archivos"
    )

    activo = models.BooleanField(
        default=True
    )

    usuario_creacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archivos_creados"
    )

    mime_type = models.CharField(
        max_length=100,
        editable=False,
        blank=True
    )

    extension = models.CharField(
        max_length=20,
        editable=False,
        blank=True
    )

    tamano_bytes = models.BigIntegerField(
        default=0,
        editable=False
    )

    checksum = models.CharField(
        max_length=64,
        editable=False,
        blank=True,
        help_text="SHA256"
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )

    actualizado = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Archivo"
        verbose_name_plural = "Archivos"
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre

    @property
    def nombre_archivo(self):
        return os.path.basename(
            self.archivo.name
        )

    # NOTA: El modelo es PASIVO. No tiene save() custom ni calcula
    # metadata. Todo análisis (mime_type, extension, checksum,
    # tamano_bytes) lo provee FileService.upload(), que es el ÚNICO
    # punto que crea instancias de Archivo.


class ArchivoRelacion(models.Model):
    """
    Relación polimórfica.
    """

    ROL_ARCHIVO = [
        ("principal", "Principal"),
        ("secundaria", "Secundaria"),
        ("galeria", "Galería"),
        ("manual", "Manual"),
        ("plano", "Plano"),
        ("video", "Video"),
        ("adjunto", "Adjunto"),
        ("otro", "Otro"),
    ]

    archivo = models.ForeignKey(
        Archivo,
        on_delete=models.CASCADE,
        related_name="relaciones"
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    object_id = models.PositiveIntegerField()

    content_object = GenericForeignKey(
        "content_type",
        "object_id"
    )

    rol = models.CharField(
        max_length=30,
        choices=ROL_ARCHIVO,
        default="otro"
    )

    orden = models.PositiveIntegerField(
        default=0
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )

    creado = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Relación de Archivo"
        verbose_name_plural = "Relaciones de Archivos"
        ordering = [
            "orden",
            "-creado",
        ]

        unique_together = (
            "content_type",
            "object_id",
            "archivo",
        )

    def __str__(self):
        return (
            f"{self.content_type} "
            f"#{self.object_id} -> "
            f"{self.archivo.nombre}"
        )