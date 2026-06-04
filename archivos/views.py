from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

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
    ArchivoUploadSimpleSerializer,
)

from .services import FileService


# ==========================================================
# TIPO ARCHIVO
# ==========================================================
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


# ==========================================================
# ARCHIVOS
# ==========================================================
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

    # -----------------------------------------
    # CONTEXTO
    # -----------------------------------------
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # -----------------------------------------
    # CREATE BLOQUEADO (punto único = upload_simple)
    # -----------------------------------------
    def create(self, request, *args, **kwargs):
        """
        Creación deshabilitada en el endpoint estándar.

        Un Archivo SOLO se crea vía FileService.upload(), expuesto
        en la acción `upload_simple`. Esto garantiza que toda
        instancia tenga metadata (mime_type, checksum, extension,
        tamaño) y validación. Crear por aquí dejaría registros sin
        analizar.
        """
        return Response(
            {
                "success": False,
                "error": (
                    "Creación no permitida en este endpoint. "
                    "Usá POST /api/archivos/archivos/upload_simple/"
                ),
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # -----------------------------------------
    # SOFT DELETE
    # -----------------------------------------
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        instance.activo = False
        instance.save(update_fields=["activo"])

        return Response(
            {
                "success": True,
                "message": "Archivo desactivado correctamente"
            },
            status=status.HTTP_200_OK,
        )

    # -----------------------------------------
    # QUERYSET CON FILTRO
    # -----------------------------------------
    def get_queryset(self):
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
            queryset = queryset.filter(activo=True)

        return queryset.order_by("-creado")

    # -----------------------------------------
    # UPLOAD SIMPLE
    # -----------------------------------------
    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_simple(self, request):
        """
        Upload simple: archivo + tipo + opcionalmente relación.
        
        Flujo:
        1. Validar request data (serializer)
        2. Llamar FileService.upload() - que hace TODO
        3. Retornar resultado
        
        FileService.upload() es el punto único:
        - valida archivo
        - analiza metadata
        - guarda en storage
        - crea Archivo en BD
        - crea ArchivoRelacion (si aplica)
        
        Request data:
        {
            "archivo": <file>,
            "tipo": <tipo_id>,
            "content_type": "producto",  [opcional]
            "object_id": 42,              [opcional]
            "rol": "principal",           [opcional]
            "observaciones": "..."        [opcional]
        }
        """

        # 1. VALIDAR REQUEST DATA
        serializer = ArchivoUploadSimpleSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data

        # 2. PREPARAR PARÁMETROS PARA FileService.upload()
        file_obj = validated_data["archivo"]
        tipo = validated_data["tipo"]
        content_type_obj = validated_data.get("content_type_obj")
        object_id = validated_data.get("object_id")
        rol = validated_data.get("rol", "principal")
        observaciones = validated_data.get("observaciones", "")
        usuario = (
            request.user
            if request.user.is_authenticated
            else None
        )

        # 3. LLAMAR FileService.upload() - PUNTO ÚNICO
        try:
            result = FileService.upload(
                file_obj=file_obj,
                tipo=tipo,
                content_type=content_type_obj,
                object_id=object_id,
                rol=rol,
                observaciones=observaciones,
                usuario=usuario,
                perform_mime_validation=True,
            )
        except ValueError as e:
            return Response(
                {
                    "success": False,
                    "error": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": f"Error interno: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 4. RETORNAR RESULTADO
        return Response(
            {
                "success": True,
                "data": result
            },
            status=status.HTTP_201_CREATED
        )


# ==========================================================
# RELACIONES
# ==========================================================
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

    serializer_class = ArchivoRelacionSerializer

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
        context = super().get_serializer_context()
        context["request"] = self.request
        return context