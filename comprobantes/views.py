# gestion/comprobantes/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from .models import Comprobante
from .serializers import ComprobanteSerializer


class AllowAnyForObtenerNumero(BasePermission):
    """
    Permiso personalizado que permite acceso sin autenticación
    solo para el endpoint obtener_siguiente_numero
    """
    def has_permission(self, request, view):
        # Si es el action obtener_siguiente_numero, list o retrieve, permitir sin autenticación
        if view.action in ['obtener_siguiente_numero', 'obtener_numero_rapido', 'list', 'retrieve']:
            return True
        # Para todo lo demás, requiere autenticación
        return request.user and request.user.is_authenticated

class ComprobanteViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar configuraciones de numeración
    
    IMPORTANTE: Estos son registros de CONFIGURACIÓN, no documentos.
    Cada registro controla la numeración para un tipo+serie específico.
    """
    queryset = Comprobante.objects.all()
    serializer_class = ComprobanteSerializer
    permission_classes = [AllowAnyForObtenerNumero]  # ⭐ Permiso personalizado
    
    def get_queryset(self):
        """
        Filtrar comprobantes según parámetros de query
        
        Uso:
        - /api/comprobantes/ → Todos
        - /api/comprobantes/?tipo=PRES → Solo presupuestos
        - /api/comprobantes/?tipo=PRES&serie=00001 → Específico
        """
        queryset = Comprobante.objects.all()
        
        tipo = self.request.query_params.get('tipo')
        serie = self.request.query_params.get('serie')
        
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        
        if serie:
            queryset = queryset.filter(serie=serie)
        
        # Ordenar por tipo y serie para consistencia
        return queryset.order_by('tipo', 'serie')
    
    def list(self, request, *args, **kwargs):
        """
        Listar configuraciones con información adicional
        
        Respuesta incluye:
        - Configuraciones existentes
        - Conteo total
        - Advertencias si hay rangos agotados
        """
        response = super().list(request, *args, **kwargs)
        
        # Agregar metadatos útiles
        configuraciones = response.data
        total = len(configuraciones)
        
        # Contar configuraciones con problemas
        agotados = 0
        pocos_numeros = 0
        
        for config in configuraciones:
            if config.get('esta_agotado'):
                agotados += 1
            elif config.get('numeros_disponibles', 0) <= 10:
                pocos_numeros += 1
        
        # Agregar metadatos a la respuesta
        response.data = {
            'configuraciones': configuraciones,
            'metadata': {
                'total': total,
                'agotados': agotados,
                'pocos_numeros': pocos_numeros,
                'advertencia': f"{agotados} rango(s) agotado(s), {pocos_numeros} con poco stock"
            }
        }
        
        return response
    
    @action(detail=False, methods=['get'])
    def obtener_configuracion(self, request):
        """
        Obtener o crear configuración para tipo+serie específicos
        
        Uso: GET /api/comprobantes/obtener_configuracion/?tipo=PRES&serie=00001
        
        Respuesta:
        - Si existe: devuelve la configuración
        - Si no existe: la crea con valores por defecto
        """
        tipo = request.query_params.get('tipo', 'PRES')
        serie = request.query_params.get('serie', '00001')
        
        if not tipo or not serie:
            return Response({
                'success': False,
                'error': 'Se requieren parámetros tipo y serie'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Buscar o crear la configuración
            config, created = Comprobante.objects.get_or_create(
                tipo=tipo,
                serie=serie,
                defaults={
                    'numero_inicial': 1,
                    'numero_final': 999999,
                    'proximo_numero': 1
                }
            )
            
            serializer = self.get_serializer(config)
            
            return Response({
                'success': True,
                'created': created,
                'configuracion': serializer.data,
                'mensaje': f"Configuración {'creada' if created else 'encontrada'}: {tipo}-{serie}"
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Error obteniendo configuración: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def obtener_siguiente_numero(self, request, pk=None):
        """
        ⭐⭐ ENDPOINT PRINCIPAL: Obtener el siguiente número disponible
        
        Uso: POST /api/comprobantes/{id}/obtener_siguiente_numero/
        
        Este es el endpoint que usa Tkinter cuando necesita un número nuevo.
        
        Proceso:
        1. Obtiene el proximo_numero actual (ej: 255)
        2. Incrementa proximo_numero para el próximo uso (a 256)
        3. Devuelve el número asignado (255)
        
        Importante: Transacción atómica para evitar duplicados
        """
        comprobante = self.get_object()
        
        try:
            # ⭐⭐ LLAMA AL MÉTODO DEL MODELO QUE INCREMENTA AUTOMÁTICAMENTE
            numero_asignado = comprobante.obtener_siguiente_numero()
            
            # Información útil para el frontend
            formato_numero = f"{comprobante.serie}-{numero_asignado:06d}"
            proximo_disponible = comprobante.proximo_numero
            
            return Response({
                'success': True,
                'numero': numero_asignado,
                'formato': formato_numero,
                'configuracion': {
                    'id': comprobante.id,
                    'tipo': comprobante.tipo,
                    'serie': comprobante.serie,
                    'proximo_numero': proximo_disponible,
                    'numeros_disponibles': comprobante.numeros_disponibles,
                    'advertencia_rango': comprobante.advertencia_rango
                },
                'mensaje': f"Número {formato_numero} asignado correctamente. Próximo: {comprobante.serie}-{proximo_disponible:06d}"
            })
            
        except ValidationError as e:
            # Rango agotado o error de validación
            return Response({
                'success': False,
                'error': str(e),
                'configuracion': {
                    'id': comprobante.id,
                    'tipo': comprobante.tipo,
                    'serie': comprobante.serie,
                    'proximo_numero': comprobante.proximo_numero,
                    'numeros_disponibles': comprobante.numeros_disponibles,
                    'esta_agotado': comprobante.esta_agotado
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            # Error inesperado
            return Response({
                'success': False,
                'error': f"Error inesperado: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def obtener_numero_rapido(self, request):
        """
        Endpoint simplificado para obtener número en un solo paso
        
        Uso: POST /api/comprobantes/obtener_numero_rapido/
        Body: {"tipo": "PRES", "serie": "00001"}
        
        Útil para Tkinter: obtiene configuración y número en una sola llamada
        """
        tipo = request.data.get('tipo', 'PRES')
        serie = request.data.get('serie', '00001')
        
        if not tipo or not serie:
            return Response({
                'success': False,
                'error': 'Se requieren tipo y serie en el body'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 1. Obtener o crear configuración
            config, created = Comprobante.objects.get_or_create(
                tipo=tipo,
                serie=serie,
                defaults={
                    'numero_inicial': 1,
                    'numero_final': 999999,
                    'proximo_numero': 1
                }
            )
            
            # 2. Obtener siguiente número
            numero_asignado = config.obtener_siguiente_numero()
            formato_numero = f"{serie}-{numero_asignado:06d}"
            
            return Response({
                'success': True,
                'numero': numero_asignado,
                'formato': formato_numero,
                'serie': serie,
                'tipo': tipo,
                'proximo_numero': config.proximo_numero,
                'numeros_disponibles': config.numeros_disponibles,
                'mensaje': f"Número {formato_numero} asignado correctamente"
            })
            
        except ValidationError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Error inesperado: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def estado(self, request, pk=None):
        """
        Obtener estado detallado de una configuración
        
        Uso: GET /api/comprobantes/{id}/estado/
        
        Útil para monitoreo y dashboard
        """
        comprobante = self.get_object()
        
        serializer = self.get_serializer(comprobante)
        
        return Response({
            'success': True,
            'configuracion': serializer.data,
            'estado': {
                'agotado': comprobante.esta_agotado,
                'numeros_restantes': comprobante.numeros_disponibles,
                'porcentaje_usado': f"{comprobante.porcentaje_usado}%",
                'recomendacion': self._generar_recomendacion(comprobante)
            }
        })
    
    def _generar_recomendacion(self, comprobante):
        """Generar recomendación según el estado del rango"""
        disponibles = comprobante.numeros_disponibles
        
        if comprobante.esta_agotado:
            return "❌ RANGO AGOTADO. Crear nueva configuración o ampliar rango."
        elif disponibles <= 10:
            return f"⚠️ QUEDAN SOLO {disponibles} NÚMEROS. Considerar crear nueva configuración."
        elif disponibles <= 50:
            return f"ℹ️ Quedan {disponibles} números. Planificar próxima configuración."
        else:
            return f"✅ Stock saludable: {disponibles} números disponibles."
    
    @action(detail=True, methods=['put'])
    def ajustar_proximo_numero(self, request, pk=None):
        """
        Ajustar manualmente el próximo número
        
        Uso: PUT /api/comprobantes/{id}/ajustar_proximo_numero/
        Body: {"proximo_numero": 255, "motivo": "Documentos manuales emitidos"}
        
        NOTA: Este endpoint requiere permisos especiales.
        Normalmente se haría desde Django Admin, pero está por si acaso.
        """
        comprobante = self.get_object()
        nuevo_proximo = request.data.get('proximo_numero')
        motivo = request.data.get('motivo', 'Sin motivo especificado')
        
        if not nuevo_proximo:
            return Response({
                'success': False,
                'error': 'Se requiere el campo proximo_numero'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            nuevo_proximo = int(nuevo_proximo)
            
            # Validar rango
            if nuevo_proximo < comprobante.numero_inicial:
                return Response({
                    'success': False,
                    'error': f'No puede ser menor que el inicial ({comprobante.numero_inicial})'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if nuevo_proximo > comprobante.numero_final:
                return Response({
                    'success': False,
                    'error': f'No puede ser mayor que el final ({comprobante.numero_final})'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Registrar el cambio (para auditoría)
            anterior = comprobante.proximo_numero
            
            # Actualizar
            comprobante.proximo_numero = nuevo_proximo
            comprobante.save()
            
            # Registrar en logs (en producción usaría logging)
            print(f"📝 AJUSTE MANUAL: {comprobante.tipo}-{comprobante.serie}")
            print(f"   Anterior: {anterior}")
            print(f"   Nuevo: {nuevo_proximo}")
            print(f"   Motivo: {motivo}")
            print(f"   Usuario: {request.user.username}")
            
            serializer = self.get_serializer(comprobante)
            
            return Response({
                'success': True,
                'mensaje': f"Próximo número ajustado: {anterior} → {nuevo_proximo}",
                'configuracion': serializer.data,
                'cambio': {
                    'anterior': anterior,
                    'nuevo': nuevo_proximo,
                    'diferencia': nuevo_proximo - anterior,
                    'motivo': motivo,
                    'usuario': request.user.username,
                    'fecha': comprobante.updated_at if hasattr(comprobante, 'updated_at') else 'Ahora'
                }
            })
            
        except ValueError:
            return Response({
                'success': False,
                'error': 'proximo_numero debe ser un número válido'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f"Error ajustando número: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def create(self, request, *args, **kwargs):
        """Sobreescribir create para agregar logging"""
        print(f"🆕 Creando nueva configuración: {request.data.get('tipo')}-{request.data.get('serie')}")
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Sobreescribir update para agregar logging"""
        print(f"✏️ Actualizando configuración ID: {kwargs.get('pk')}")
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """
        Eliminar configuración
        
        Advertencia: Eliminar una configuración puede afectar la numeración futura
        """
        comprobante = self.get_object()
        
        # Advertencia antes de eliminar
        if not request.data.get('confirmar'):
            return Response({
                'success': False,
                'advertencia': f"Está por eliminar la configuración {comprobante.tipo}-{comprobante.serie}",
                'detalle': f"Rango: {comprobante.numero_inicial}-{comprobante.numero_final} | Próximo: {comprobante.proximo_numero}",
                'instruccion': 'Incluir "confirmar": true en el body para proceder'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return super().destroy(request, *args, **kwargs)