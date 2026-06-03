# gestion/backend/archivos/views.py

from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response

from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
)

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import (
    SearchFilter,
    OrderingFilter,
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

    queryset = (
        TipoArchivo.objects
        .filter(activo=True)
        .order_by("nombre")
    )

    serializer_class = TipoArchivoSerializer

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "nombre",
        "descripcion",
    ]

    ordering_fields = [
        "nombre",
    ]

    ordering = [
        "nombre",
    ]


class ArchivoViewSet(viewsets.ModelViewSet):
    """
    Repositorio central de archivos.
    """

    queryset = (
        Archivo.objects
        .select_related("tipo")
        .order_by("-creado")
    )

    serializer_class = ArchivoSerializer

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "tipo",
        "activo",
        "extension",
    ]

    search_fields = [
        "nombre",
        "nombre_original",
        "descripcion",
    ]

    ordering_fields = [
        "nombre",
        "creado",
        "tamano_bytes",
    ]

    ordering = [
        "-creado",
    ]

    def get_serializer_context(self):
        """
        Agrega request al contexto.
        """

        context = super().get_serializer_context()

        context.update({
            "request": self.request
        })

        return context

    def perform_create(self, serializer):
        """
        Guarda automáticamente el usuario
        que cargó el archivo.
        """

        serializer.save(
            usuario_creacion=self.request.user
        )

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete.

        No elimina físicamente el archivo.
        """

        instance = self.get_object()

        instance.activo = False
        instance.save(
            update_fields=["activo"]
        )

        return Response(
            {
                "detail": (
                    "Archivo desactivado "
                    "correctamente."
                )
            },
            status=status.HTTP_200_OK,
        )

    def get_queryset(self):
        """
        Permite ocultar archivos inactivos
        por defecto.
        """

        queryset = (
            Archivo.objects
            .select_related("tipo")
        )

        incluir_inactivos = (
            self.request.query_params.get(
                "incluir_inactivos",
                "false"
            ).lower()
        )

        if incluir_inactivos != "true":
            queryset = queryset.filter(
                activo=True
            )

        return queryset.order_by(
            "-creado"
        )


class ArchivoRelacionViewSet(viewsets.ModelViewSet):
    """
    Relaciones polimórficas entre archivos
    y cualquier entidad del sistema.
    """

    queryset = (
        ArchivoRelacion.objects
        .select_related(
            "archivo",
            "content_type",
        )
        .order_by(
            "orden",
            "-creado",
        )
    )

    serializer_class = (
        ArchivoRelacionSerializer
    )

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "content_type",
        "object_id",
        "rol",
    ]

    ordering_fields = [
        "orden",
        "creado",
    ]

    ordering = [
        "orden",
        "-creado",
    ]

    def get_serializer_context(self):
        """
        Agrega request al contexto.
        """

        context = super().get_serializer_context()

        context.update({
            "request": self.request
        })

        return context