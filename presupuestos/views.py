# gestion/presupuestos/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Presupuesto, PresupuestoAdjunto
from .serializers import PresupuestoSerializer, PresupuestoAdjuntoSerializer


class AllowAnyForCreate(BasePermission):
    """
    Permiso personalizado que permite crear presupuestos sin autenticación
    pero requiere autenticación para otras operaciones
    """
    def has_permission(self, request, view):
        # Permitir sin autenticación: crear presupuestos y listar
        if view.action in ['create', 'list', 'retrieve']:
            return True
        # Para todo lo demás (update, delete, etc.), requiere autenticación
        return request.user and request.user.is_authenticated


class PresupuestoViewSet(viewsets.ModelViewSet):
    queryset = Presupuesto.objects.all()
    serializer_class = PresupuestoSerializer
    permission_classes = [AllowAnyForCreate]  # ⭐ Permiso personalizado
   
    def get_queryset(self):
        queryset = Presupuesto.objects.all()
        
        # Excluir anulados por defecto (opcional)
        if not self.request.query_params.get('incluir_anulados'):
            queryset = queryset.exclude(estado='anulado')
        
        return queryset

    def perform_create(self, serializer):
        # Si hay usuario autenticado, usarlo; si no, usar el primer superusuario
        if self.request.user and self.request.user.is_authenticated:
            serializer.save(creado_por=self.request.user)
        else:
            # Usuario por defecto para peticiones sin autenticación (Tkinter)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            default_user = User.objects.filter(is_superuser=True).first()
            if default_user:
                serializer.save(creado_por=default_user)
            else:
                # Si no hay superusuario, crear uno temporal
                default_user = User.objects.create_superuser(
                    username='sistema',
                    email='sistema@example.com',
                    password='sistema123'
                )
                serializer.save(creado_por=default_user)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        """
        Anular un presupuesto
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
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def presupuestos_anulados(self, request):
        """
        Listar solo presupuestos anulados
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
        Estadísticas de presupuestos
        """
        total = Presupuesto.objects.count()
        por_estado = Presupuesto.objects.values('estado').annotate(
            count=Count('id'),
            total_monto=Sum('total')
        )
        
        return Response({
            'total': total,
            'por_estado': list(por_estado)
        })


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