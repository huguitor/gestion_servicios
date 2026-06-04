from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
)

from django.contrib.contenttypes.models import ContentType

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

    # -----------------------------------------
    # UPLOAD MÚLTIPLE
    # -----------------------------------------
    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_multiple(self, request):
        """
        Carga varios archivos de una sola vez a la biblioteca.

        Request (multipart):
        - archivos: <file> (repetido N veces)   [requerido]
        - tipo: <tipo_id>                        [requerido]
        - content_type: "producto"              [opcional] sube y vincula
        - object_id: 42                          [opcional]
        - rol: "galeria"                        [opcional, default principal]
        - observaciones: "..."                  [opcional]

        Reusa FileService.upload() (punto único) por cada archivo, cada
        uno en su propia transacción. Deduplica por checksum SHA256: si ya
        existe un Archivo activo con el mismo contenido, lo reutiliza (y, si
        corresponde, crea la relación) en vez de volver a guardarlo.

        Devuelve {creados, duplicados, errores} sin abortar el lote por un
        archivo fallido.
        """
        from .models import Archivo, ArchivoRelacion

        files = request.FILES.getlist("archivos")
        if not files:
            return Response(
                {
                    "success": False,
                    "error": "No se enviaron archivos (campo 'archivos').",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # tipo (requerido)
        tipo_id = request.data.get("tipo")
        try:
            tipo = TipoArchivo.objects.get(pk=tipo_id)
        except (TipoArchivo.DoesNotExist, ValueError, TypeError):
            return Response(
                {"success": False, "error": "tipo inválido o no enviado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # relación opcional (subir + vincular en lote)
        content_type_str = (request.data.get("content_type") or "").strip()
        object_id = request.data.get("object_id") or None
        rol = request.data.get("rol") or "principal"
        observaciones = request.data.get("observaciones") or ""

        content_type_obj = None
        if content_type_str:
            if not object_id:
                return Response(
                    {
                        "success": False,
                        "error": "object_id es requerido si se envía content_type.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                content_type_obj = ContentType.objects.get(model=content_type_str)
            except ContentType.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "error": f"Modelo no existe: {content_type_str}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        usuario = request.user if request.user.is_authenticated else None

        creados = []
        duplicados = []
        errores = []

        for file_obj in files:
            try:
                # Dedup por checksum: ¿ya existe el mismo contenido?
                checksum = FileService.analyze_file(file_obj).get("checksum", "")
                file_obj.seek(0)

                existente = (
                    Archivo.objects.filter(checksum=checksum, activo=True).first()
                    if checksum
                    else None
                )

                if existente:
                    relacion_id = None
                    if content_type_obj and object_id:
                        relacion, _creada = ArchivoRelacion.objects.get_or_create(
                            archivo=existente,
                            content_type=content_type_obj,
                            object_id=object_id,
                            defaults={"rol": rol, "observaciones": observaciones},
                        )
                        relacion_id = relacion.id
                    duplicados.append(
                        {
                            "archivo": file_obj.name,
                            "archivo_id": existente.id,
                            "relacion_id": relacion_id,
                            "reutilizado": True,
                        }
                    )
                    continue

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
                creados.append(result)

            except ValueError as e:
                errores.append({"archivo": file_obj.name, "error": str(e)})
            except Exception as e:
                errores.append(
                    {"archivo": file_obj.name, "error": f"Error interno: {str(e)}"}
                )

        return Response(
            {
                "success": True,
                "creados": creados,
                "duplicados": duplicados,
                "errores": errores,
            },
            status=status.HTTP_201_CREATED,
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

    def get_queryset(self):
        """
        Permite filtrar por nombre de modelo (`content_type_model`) además
        del id numérico, para que el frontend liste los archivos de una
        entidad sin conocer el id de ContentType.
        Ej: ?content_type_model=producto&object_id=5
        """
        queryset = super().get_queryset()

        model_name = self.request.query_params.get("content_type_model")
        if model_name:
            try:
                ct = ContentType.objects.get(model=model_name.strip().lower())
                queryset = queryset.filter(content_type=ct)
            except ContentType.DoesNotExist:
                return queryset.none()

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context