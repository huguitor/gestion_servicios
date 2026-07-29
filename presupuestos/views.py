# gestion/backend/presupuestos/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Count
from django.http import HttpResponse

from .models import Presupuesto, PresupuestoAdjunto
from .serializers import (
    PresupuestoAdjuntoSerializer,
    PresupuestoSerializer,
    SeleccionAdjuntosSerializer,
)
from .pdf_generator import filename_for, generar_pdf_presupuesto
from .photo_packages import (
    generar_pdf_fotografico,
    generar_zip_fotografico,
    nombre_paquete,
    validar_adjuntos_fotograficos,
)
from licensing.decorators import require_module


class PresupuestoViewSet(viewsets.ModelViewSet):
    """
    ViewSet de presupuestos.

    Seguridad:
    - Solo usuarios admin/staff pueden acceder.
    - Ya no se permite crear/listar/ver presupuestos sin autenticación.
    - Ya no se crea automáticamente ningún superusuario.
    """

    queryset = Presupuesto.objects.all()
    serializer_class = PresupuestoSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """
        Por defecto excluye presupuestos anulados.
        Si se envía ?incluir_anulados=1, devuelve todos.
        """
        queryset = Presupuesto.objects.all()

        if not self.request.query_params.get('incluir_anulados'):
            queryset = queryset.exclude(estado='anulado')

        return queryset

    def perform_create(self, serializer):
        """
        Guarda el presupuesto usando el usuario autenticado actual.

        Si no hay usuario válido, DRF bloquea antes por IsAdminUser.
        """
        serializer.save(creado_por=self.request.user)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """
        Generar y devolver el PDF del presupuesto.
        """
        presupuesto = self.get_object()

        try:
            pdf_bytes = generar_pdf_presupuesto(presupuesto)
        except Exception as exc:
            return Response(
                {'error': f'No se pudo generar el PDF: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{filename_for(presupuesto)}"'
        )
        return response

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        """
        Anular un presupuesto.
        """
        presupuesto = self.get_object()
        motivo = request.data.get('motivo', '')

        try:
            presupuesto.anular(request.user, motivo)
            serializer = self.get_serializer(presupuesto)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=['get'])
    def presupuestos_anulados(self, request):
        """
        Listar solo presupuestos anulados.
        """
        anulados = Presupuesto.objects.filter(estado='anulado')

        page = self.paginate_queryset(anulados)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(anulados, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas generales de presupuestos.
        """
        total = Presupuesto.objects.count()
        por_estado = Presupuesto.objects.values('estado').annotate(
            count=Count('id'),
            total_monto=Sum('total'),
        )

        return Response({
            'total': total,
            'por_estado': list(por_estado),
        })


class PresupuestoAdjuntoViewSet(viewsets.ModelViewSet):
    """
    ViewSet de adjuntos de presupuestos.

    Solo usuarios admin/staff pueden acceder.
    """

    queryset = PresupuestoAdjunto.objects.all()
    serializer_class = PresupuestoAdjuntoSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = PresupuestoAdjunto.objects.select_related(
            'presupuesto',
            'subido_por',
        )

        presupuesto_pk = self.kwargs.get('presupuesto_pk')
        if presupuesto_pk:
            queryset = queryset.filter(presupuesto_id=presupuesto_pk)

        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        return queryset

    def perform_create(self, serializer):
        presupuesto_pk = self.kwargs.get('presupuesto_pk')

        if presupuesto_pk:
            serializer.save(
                subido_por=self.request.user,
                presupuesto_id=presupuesto_pk,
            )
        else:
            serializer.save(subido_por=self.request.user)

    @action(detail=False, methods=['post'], url_path='pdf')
    @require_module('presupuestos')
    def pdf_fotografico(self, request, presupuesto_pk=None):
        presupuesto = self._get_presupuesto(presupuesto_pk)
        seleccion = SeleccionAdjuntosSerializer(data=request.data)
        seleccion.is_valid(raise_exception=True)
        adjuntos = validar_adjuntos_fotograficos(
            presupuesto=presupuesto,
            adjuntos=self.get_queryset().filter(
                id__in=seleccion.validated_data['adjunto_ids']
            ),
            requested_ids=seleccion.validated_data['adjunto_ids'],
        )
        contenido = generar_pdf_fotografico(
            presupuesto=presupuesto,
            adjuntos=adjuntos,
        )
        return self._download_response(
            contenido,
            nombre_paquete(presupuesto, 'pdf'),
            'application/pdf',
        )

    @action(detail=False, methods=['post'], url_path='zip')
    @require_module('presupuestos')
    def zip_fotografico(self, request, presupuesto_pk=None):
        presupuesto = self._get_presupuesto(presupuesto_pk)
        seleccion = SeleccionAdjuntosSerializer(data=request.data)
        seleccion.is_valid(raise_exception=True)
        adjuntos = validar_adjuntos_fotograficos(
            presupuesto=presupuesto,
            adjuntos=self.get_queryset().filter(
                id__in=seleccion.validated_data['adjunto_ids']
            ),
            requested_ids=seleccion.validated_data['adjunto_ids'],
        )
        contenido = generar_zip_fotografico(adjuntos=adjuntos)
        return self._download_response(
            contenido,
            nombre_paquete(presupuesto, 'zip'),
            'application/zip',
        )

    @staticmethod
    def _get_presupuesto(presupuesto_pk):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(
            Presupuesto.objects.select_related('cliente', 'comprobante'),
            pk=presupuesto_pk,
        )

    @staticmethod
    def _download_response(contenido, filename, content_type):
        response = HttpResponse(contenido, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'])
    def tipos_disponibles(self, request):
        """
        Lista los tipos de adjuntos disponibles.
        """
        tipos = []

        for tipo_val, tipo_label in PresupuestoAdjunto.TIPO_CHOICES:
            count = PresupuestoAdjunto.objects.filter(tipo=tipo_val).count()
            tipos.append({
                'valor': tipo_val,
                'label': tipo_label,
                'count': count,
                'icono': tipo_label.split(' ')[0],
            })

        return Response(tipos)

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas de uso de adjuntos.
        """
        queryset = self.get_queryset()

        stats = {
            'total_archivos': queryset.count(),
            'tamaño_total': queryset.aggregate(total=Sum('tamaño'))['total'] or 0,
            'por_tipo': list(queryset.values('tipo').annotate(
                count=Count('id'),
                tamaño_total=Sum('tamaño'),
            )),
        }

        return Response(stats)

    @action(detail=True, methods=['post'])
    def reemplazar(self, request, pk=None):
        """
        Reemplazar un archivo existente.
        """
        adjunto = self.get_object()
        nuevo_archivo = request.FILES.get('archivo')

        if not nuevo_archivo:
            return Response(
                {'error': 'No se proporcionó un nuevo archivo'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        adjunto.archivo = nuevo_archivo
        adjunto.tamaño = nuevo_archivo.size
        adjunto.extension = adjunto.obtener_extension()
        adjunto.version += 1
        adjunto.save()

        serializer = self.get_serializer(adjunto)
        return Response(serializer.data)
