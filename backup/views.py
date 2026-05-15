# gestion/backup/views.py
#
# Endpoints DRF para backup/restauración. Solo accesibles a superusers
# (operación destructiva — no es para usuarios normales).

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from django.http import HttpResponse

from .exporters import (
    BackupResult,
    export_clientes,
    export_configuracion,
    export_database,
    export_media,
    export_presupuestos,
    export_productos,
    export_remitos,
    export_servicios,
    export_todo,
)
from .importers import (
    IMPORTERS_BY_TIPO,
    RestoreError,
    restore_todo,
)
from .storage import (
    delete_backup,
    get_backup_path,
    list_backups,
    save_to_disk,
)


class IsSuperUser(BasePermission):
    """Solo superusers pueden hacer backup/restore."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_superuser
        )


def _file_response(result: BackupResult) -> HttpResponse:
    """
    Doble efecto: guarda en /data/backups/ Y devuelve el archivo al browser.
    """
    save_to_disk(result.filename, result.data)
    response = HttpResponse(result.data, content_type=result.content_type)
    response['Content-Disposition'] = f'attachment; filename="{result.filename}"'
    response['Content-Length'] = str(len(result.data))
    return response


# ---------------------------------------------------------------------------
# EXPORTACIÓN — un endpoint GET por tipo
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_clientes(request):
    return _file_response(export_clientes())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_productos(request):
    return _file_response(export_productos())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_servicios(request):
    return _file_response(export_servicios())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_presupuestos(request):
    return _file_response(export_presupuestos())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_remitos(request):
    return _file_response(export_remitos())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_configuracion(request):
    return _file_response(export_configuracion())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_media(request):
    return _file_response(export_media())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_database(request):
    return _file_response(export_database())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def backup_todo(request):
    """
    Acepta query param ?incluir=clientes,productos,... para limitar el contenido.
    Sin param → incluye todos.
    """
    incluir = request.query_params.get('incluir', '').strip()
    items = [x.strip() for x in incluir.split(',') if x.strip()] if incluir else None
    return _file_response(export_todo(items))


# ---------------------------------------------------------------------------
# RESTAURACIÓN — POST con multipart/form-data, campo 'archivo'
# ---------------------------------------------------------------------------

def _do_restore(request, tipo: str):
    archivo = request.FILES.get('archivo')
    if not archivo:
        return Response(
            {'error': "Falta el campo 'archivo' (multipart/form-data)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    importer = IMPORTERS_BY_TIPO.get(tipo)
    if not importer:
        return Response(
            {'error': f"Tipo '{tipo}' no soportado para restauración."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        summary = importer(archivo.read())
    except RestoreError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f'Error inesperado al restaurar: {e}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(summary.as_dict())


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_clientes(request):
    return _do_restore(request, 'clientes')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_productos(request):
    return _do_restore(request, 'productos')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_servicios(request):
    return _do_restore(request, 'servicios')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_presupuestos(request):
    return _do_restore(request, 'presupuestos')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_remitos(request):
    return _do_restore(request, 'remitos')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_configuracion(request):
    return _do_restore(request, 'configuracion')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def restore_todo_view(request):
    """Restaura un ZIP master generado por backup_todo."""
    archivo = request.FILES.get('archivo')
    if not archivo:
        return Response(
            {'error': "Falta el campo 'archivo'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        summaries = restore_todo(archivo.read())
    except RestoreError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f'Error inesperado al restaurar: {e}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response({
        'restaurados': len(summaries),
        'detalle': [s.as_dict() for s in summaries],
    })


# ---------------------------------------------------------------------------
# HISTORIAL — listar, descargar y borrar backups guardados en disco
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsSuperUser])
def historial_list(request):
    return Response(list_backups())


@api_view(['GET'])
@permission_classes([IsSuperUser])
def historial_download(request, filename: str):
    path = get_backup_path(filename)
    if not path:
        return Response({'error': 'Archivo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if filename.endswith('.json'):
        ctype = 'application/json'
    elif filename.endswith('.zip'):
        ctype = 'application/zip'
    else:
        ctype = 'application/octet-stream'

    response = HttpResponse(path.read_bytes(), content_type=ctype)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['DELETE'])
@permission_classes([IsSuperUser])
def historial_delete(request, filename: str):
    if delete_backup(filename):
        return Response({'eliminado': filename})
    return Response({'error': 'Archivo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Info: tipos disponibles para el frontend (UI)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tipos_disponibles(request):
    """
    Lista de tipos que se pueden exportar (para armar los checkboxes).
    No requiere superuser — el frontend lo consulta para renderizar la UI.
    """
    return Response({
        'tipos': [
            {'key': 'clientes', 'label': 'Clientes', 'extension': 'json'},
            {'key': 'productos', 'label': 'Productos (con fotos y planos)', 'extension': 'zip'},
            {'key': 'servicios', 'label': 'Servicios (con imágenes y adjuntos)', 'extension': 'zip'},
            {'key': 'presupuestos', 'label': 'Presupuestos (con adjuntos)', 'extension': 'zip'},
            {'key': 'remitos', 'label': 'Remitos (con adjuntos)', 'extension': 'zip'},
            {'key': 'configuracion', 'label': 'Configuración (con logos)', 'extension': 'zip'},
            {'key': 'media', 'label': 'Media completa (toda la carpeta)', 'extension': 'zip'},
            {'key': 'database', 'label': 'Base de datos SQLite', 'extension': 'db'},
        ],
    })
