# gestion/backend/pedidos_internos/services/derivacion_service.py
"""
Compatibilidad documental — Fase 2.

La trazabilidad fina de derivaciones (modelo PedidoDerivacion dedicado
y reglas de SLA / tiempos máximos) se implementará en una fase posterior.
La derivación operativa actual se resuelve exclusivamente en
`workflow_service.derivar`, mediante PedidoMovimiento y un nuevo
PedidoDestino. Este módulo queda reservado para una futura trazabilidad
específica de derivaciones y reglas de SLA propias de esa operación.
"""
