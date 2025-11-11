# gestion/presupuestos/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from .models import Presupuesto, PresupuestoAdjunto
from .serializers import PresupuestoSerializer, PresupuestoAdjuntoSerializer

class PresupuestoViewSet(viewsets.ModelViewSet):
    queryset = Presupuesto.objects.all()
    serializer_class = PresupuestoSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

class PresupuestoAdjuntoViewSet(viewsets.ModelViewSet):
    queryset = PresupuestoAdjunto.objects.all()
    serializer_class = PresupuestoAdjuntoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PresupuestoAdjunto.objects.select_related(
            'presupuesto', 'subido_por'
        )
        
        # Filtrar por presupuesto si viene en la URL
        presupuesto_pk = self.kwargs.get('presupuesto_pk')
        if presupuesto_pk:
            queryset = queryset.filter(presupuesto_id=presupuesto_pk)
        
        # Filtros adicionales por query params
        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        return queryset

    def perform_create(self, serializer):
        presupuesto_pk = self.kwargs.get('presupuesto_pk')
        if presupuesto_pk:
            serializer.save(
                subido_por=self.request.user,
                presupuesto_id=presupuesto_pk
            )
        else:
            serializer.save(subido_por=self.request.user)

    @action(detail=False, methods=['get'])
    def tipos_disponibles(self, request):
        """
        Lista los tipos de adjuntos disponibles
        """
        tipos = []
        for tipo_val, tipo_label in PresupuestoAdjunto.TIPO_CHOICES:
            count = PresupuestoAdjunto.objects.filter(tipo=tipo_val).count()
            tipos.append({
                'valor': tipo_val,
                'label': tipo_label,
                'count': count,
                'icono': tipo_label.split(' ')[0]  # Emoji del icono
            })
        
        return Response(tipos)

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Estadísticas de uso de adjuntos
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_archivos': queryset.count(),
            'tamaño_total': queryset.aggregate(total=Sum('tamaño'))['total'] or 0,
            'por_tipo': list(queryset.values('tipo').annotate(
                count=Count('id'),
                tamaño_total=Sum('tamaño')
            ))
        }
        
        return Response(stats)

    @action(detail=True, methods=['post'])
    def reemplazar(self, request, pk=None):
        """
        Reemplazar un archivo existente (crea nueva versión)
        """
        adjunto = self.get_object()
        nuevo_archivo = request.FILES.get('archivo')
        
        if not nuevo_archivo:
            return Response(
                {'error': 'No se proporcionó un nuevo archivo'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Actualizar el archivo y recalcular campos
        adjunto.archivo = nuevo_archivo
        adjunto.tamaño = nuevo_archivo.size
        adjunto.extension = adjunto.obtener_extension()
        adjunto.version += 1
        adjunto.save()
        
        serializer = self.get_serializer(adjunto)
        return Response(serializer.data)