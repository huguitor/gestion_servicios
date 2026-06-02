# gestion/backend/archivos/views.py

from rest_framework import viewsets
from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
)

from .models import (
    TipoArchivo,
    Archivo,
    ArchivoRelacion,
)

from .serializers import (
    TipoArchivoSerializer,
    ArchivoSerializer,
    ArchivoRelacionSerializer,
)


class TipoArchivoViewSet(viewsets.ModelViewSet):
    """
    Catálogo de tipos de archivos.
    """

    queryset = TipoArchivo.objects.filter(
        activo=True
    ).order_by("nombre")

    serializer_class = TipoArchivoSerializer


class ArchivoViewSet(viewsets.ModelViewSet):
    """
    Repositorio central de archivos.
    """

    queryset = Archivo.objects.select_related(
        "tipo"
    ).order_by("-creado")

    serializer_class = ArchivoSerializer

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()

        context.update({
            "request": self.request
        })

        return context


class ArchivoRelacionViewSet(viewsets.ModelViewSet):
    """
    Relaciones polimórficas entre archivos
    y cualquier entidad del sistema.
    """

    queryset = ArchivoRelacion.objects.select_related(
        "archivo",
        "content_type",
    ).order_by(
        "orden",
        "-creado",
    )

    serializer_class = ArchivoRelacionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()

        context.update({
            "request": self.request
        })

        return context