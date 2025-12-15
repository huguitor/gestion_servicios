# gestion/remitos/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db import models  # ← AGREGADO para usar models.Count
from django.db.models.functions import TruncMonth  # ← AGREGADO
from django.core.exceptions import ValidationError  # ← AGREGADO
from .models import Remito, ItemRemito, RemitoAdjunto
from .serializers import RemitoSerializer, ItemRemitoSerializer, RemitoAdjuntoSerializer


class RemitoViewSet(viewsets.ModelViewSet):
    queryset = Remito.objects.all()
    serializer_class = RemitoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por cliente (si se especifica)
        cliente = self.request.query_params.get('cliente', None)
        if cliente:
            queryset = queryset.filter(cliente__nombre__icontains=cliente)  # ← CORREGIDO: usar cliente__nombre
        
        # Filtrar por estado
        estado = self.request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Filtrar por fecha
        fecha_desde = self.request.query_params.get('fecha_desde', None)
        fecha_hasta = self.request.query_params.get('fecha_hasta', None)
        if fecha_desde:
            queryset = queryset.filter(fecha_emision__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_emision__lte=fecha_hasta)
        
        # Filtrar por presupuesto relacionado
        presupuesto = self.request.query_params.get('presupuesto', None)
        if presupuesto:
            queryset = queryset.filter(presupuesto_relacionado__icontains=presupuesto)
        
        # Filtrar por licitación/orden
        licitacion = self.request.query_params.get('licitacion', None)
        if licitacion:
            queryset = queryset.filter(licitacion_orden__icontains=licitacion)
        
        # Filtrar por serie/número
        numero = self.request.query_params.get('numero', None)
        if numero:
            queryset = queryset.filter(numero=numero)
        
        # Filtrar por comprobante
        comprobante = self.request.query_params.get('comprobante', None)
        if comprobante:
            queryset = queryset.filter(comprobante_id=comprobante)
        
        return queryset
    
    def perform_create(self, serializer):
        # Asignar usuario creador automáticamente
        serializer.save(creado_por=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambiar estado del remito"""
        remito = self.get_object()
        nuevo_estado = request.data.get('estado')
        motivo = request.data.get('motivo', '')
        
        estados_validos = [choice[0] for choice in Remito.ESTADO_CHOICES]
        
        if nuevo_estado not in estados_validos:
            return Response(
                {"error": f"Estado inválido. Válidos: {estados_validos}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar transiciones de estado
        if nuevo_estado == 'anulado':
            if remito.estado == 'entregado':
                return Response(
                    {"error": "No se puede anular un remito entregado"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not motivo:
                return Response(
                    {"error": "Se requiere un motivo para anular"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            remito.motivo_anulacion = motivo
        
        remito.estado = nuevo_estado
        remito.save()
        
        return Response({
            "mensaje": f"Estado actualizado a {nuevo_estado}",
            "remito": RemitoSerializer(remito).data
        })
    
    @action(detail=False, methods=['get'])
    def buscar_por_cliente(self, request):
        """Buscar remitos por nombre de cliente"""
        cliente = request.query_params.get('cliente', '')
        
        if not cliente:
            return Response(
                {"error": "Debe especificar un cliente"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        remitos = self.get_queryset().filter(cliente__nombre__icontains=cliente)  # ← CORREGIDO
        serializer = self.get_serializer(remitos, many=True)
        
        return Response({
            "cliente": cliente,
            "total": remitos.count(),
            "remitos": serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas de remitos"""
        total = Remito.objects.count()
        por_estado = Remito.objects.values('estado').annotate(
            count=models.Count('id')
        )
        
        # Remitos por mes
        por_mes = Remito.objects.annotate(
            mes=TruncMonth('fecha_emision')
        ).values('mes').annotate(
            count=models.Count('id')
        ).order_by('-mes')[:12]
        
        # Top 5 clientes con más remitos
        top_clientes = Remito.objects.values(
            'cliente__nombre', 'cliente__id'
        ).annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        # Remitos por año actual
        from datetime import datetime
        año_actual = datetime.now().year
        remitos_año_actual = Remito.objects.filter(
            fecha_emision__year=año_actual
        ).count()
        
        return Response({
            'total': total,
            'remitos_año_actual': remitos_año_actual,
            'por_estado': list(por_estado),
            'por_mes': list(por_mes),
            'top_clientes': list(top_clientes)
        })
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Obtener items de un remito específico"""
        remito = self.get_object()
        items = remito.items.all()
        serializer = ItemRemitoSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def agregar_item(self, request, pk=None):
        """Agregar item a un remito"""
        remito = self.get_object()
        
        # Validar que el remito no esté anulado
        if remito.estado == 'anulado':
            return Response(
                {"error": "No se puede agregar items a un remito anulado"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ItemRemitoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(remito=remito)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        """Anular un remito"""
        remito = self.get_object()
        motivo = request.data.get('motivo', '')
        
        if not motivo:
            return Response(
                {"error": "Se requiere un motivo para anular"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            remito.anular(request.user, motivo)
            return Response({
                "mensaje": "Remito anulado correctamente",
                "remito": RemitoSerializer(remito).data
            })
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def proximo_numero(self, request):
        """Obtener próximo número disponible para remitos"""
        from comprobantes.models import Comprobante
        
        comprobante = Comprobante.objects.filter(tipo='REMI').first()
        if not comprobante:
            return Response(
                {"error": "No hay configuración de numeración para remitos"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # CORRECCIÓN: usar proximo_numero en lugar de numero_comienzo
        proximo = comprobante.proximo_numero
        
        # Validar que no exceda el rango
        if proximo > comprobante.numero_final:
            return Response(
                {"error": f"No hay números disponibles. Límite: {comprobante.numero_final}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            "proximo_numero": proximo,
            "serie": comprobante.serie,
            "comprobante_id": comprobante.id,
            "numeros_disponibles": comprobante.numeros_disponibles,  # ← Usar propiedad
            "numero_inicial": comprobante.numero_inicial,
            "numero_final": comprobante.numero_final,
            "porcentaje_usado": comprobante.porcentaje_usado
        })
    
    @action(detail=True, methods=['get', 'post'])
    def adjuntos(self, request, pk=None):
        """Gestión de adjuntos del remito"""
        remito = self.get_object()
        
        if request.method == 'GET':
            adjuntos = remito.adjuntos.all()
            serializer = RemitoAdjuntoSerializer(adjuntos, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = RemitoAdjuntoSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save(remito=remito, subido_por=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Datos para dashboard"""
        
        # Conteo por estado
        por_estado = Remito.objects.values('estado').annotate(
            count=models.Count('id')
        )
        
        # Remitos del mes actual
        from django.utils import timezone
        hoy = timezone.now()
        primer_dia_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        remitos_mes_actual = Remito.objects.filter(
            fecha_emision__gte=primer_dia_mes
        ).count()
        
        # Últimos 5 remitos
        ultimos_remitos = Remito.objects.select_related('cliente', 'comprobante').order_by('-creado')[:5]
        ultimos_serializer = RemitoSerializer(ultimos_remitos, many=True)
        
        # Remitos pendientes
        pendientes = Remito.objects.filter(estado='pendiente').count()
        
        return Response({
            'por_estado': list(por_estado),
            'remitos_mes_actual': remitos_mes_actual,
            'pendientes': pendientes,
            'ultimos_remitos': ultimos_serializer.data,
            'total': Remito.objects.count()
        })
    
    @action(detail=True, methods=['post'])
    def duplicar(self, request, pk=None):
        """Duplicar un remito"""
        remito = self.get_object()
        
        try:
            with transaction.atomic():
                # Crear nuevo remito con los mismos datos
                nuevo_remito = Remito.objects.create(
                    comprobante=remito.comprobante,
                    cliente=remito.cliente,
                    fecha_emision=timezone.now().date(),
                    origen=remito.origen,
                    destino=remito.destino,
                    presupuesto_relacionado=remito.presupuesto_relacionado,
                    licitacion_orden=remito.licitacion_orden,
                    numero_referencia=remito.numero_referencia,
                    observaciones=f"Copiado de {remito.numero_formateado}\n" + remito.observaciones,
                    estado='borrador',
                    creado_por=request.user
                )
                
                # Duplicar items
                for item in remito.items.all():
                    ItemRemito.objects.create(
                        remito=nuevo_remito,
                        codigo=item.codigo,
                        descripcion=item.descripcion,
                        cantidad=item.cantidad,
                        unidad_medida=item.unidad_medida,
                        observaciones=item.observaciones,
                        orden=item.orden
                    )
                
                serializer = self.get_serializer(nuevo_remito)
                return Response({
                    "mensaje": f"Remito duplicado como {nuevo_remito.numero_formateado}",
                    "remito": serializer.data
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {"error": f"Error al duplicar: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ItemRemitoViewSet(viewsets.ModelViewSet):
    queryset = ItemRemito.objects.all()
    serializer_class = ItemRemitoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por remito si se especifica
        remito_id = self.request.query_params.get('remito', None)
        if remito_id:
            queryset = queryset.filter(remito_id=remito_id)
        
        # Filtrar por código
        codigo = self.request.query_params.get('codigo', None)
        if codigo:
            queryset = queryset.filter(codigo__icontains=codigo)
        
        # Filtrar por descripción
        descripcion = self.request.query_params.get('descripcion', None)
        if descripcion:
            queryset = queryset.filter(descripcion__icontains=descripcion)
        
        return queryset


class RemitoAdjuntoViewSet(viewsets.ModelViewSet):
    queryset = RemitoAdjunto.objects.all()
    serializer_class = RemitoAdjuntoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por remito
        remito_id = self.request.query_params.get('remito', None)
        if remito_id:
            queryset = queryset.filter(remito_id=remito_id)
        
        # Filtrar por tipo
        tipo = self.request.query_params.get('tipo', None)
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(subido_por=self.request.user)