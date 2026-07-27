# Pedidos internos — prueba operativa

Esta guía valida el circuito completo sin usar credenciales reales. Preparar usuarios de prueba con membresías activas y reglas SLA controladas. Registrar en cada escenario el número de pedido y la hora de inicio.

## Preparación

- `SOLICITANTE`: miembro activo de `ORIGEN`.
- `OPERADOR_A`: miembro activo de `TALLER`.
- `OPERADOR_B`: miembro activo de `COMPRAS`.
- `SIN_MEMBRESIA`: usuario autenticado sin membresía en `TALLER`.
- Verificar que `pedidos_internos` esté habilitado por licencia.
- No reutilizar pedidos de producción.

## Escenario 1 — Pedido simple

| Paso | Usuario / sector | Acción | Resultado esperado |
|---|---|---|---|
| 1 | SOLICITANTE / ORIGEN | Crear un pedido normal con destino TALLER y un concepto libre | Toast de creación y apertura del detalle |
| 2 | SOLICITANTE | Abrir “Mis pedidos” | Pedido pendiente, 0 de 1 resuelto |
| 3 | OPERADOR_A / TALLER | Abrir dashboard y bandeja | Aumentan total, pendientes y sin leer |
| 4 | OPERADOR_A | Marcar leído, tomar, iniciar y resolver | Responsable visible, timeline completo, SLA actualizado |
| 5 | SOLICITANTE | Consultar detalle y “Mis pedidos” | Estado global resuelto y 1 de 1 destino resuelto |

Pantallas que deben actualizarse: dashboard, bandeja, detalle, timeline y “Mis pedidos”.

## Escenario 2 — Dos destinos

| Paso | Usuario / sector | Acción | Resultado esperado |
|---|---|---|---|
| 1 | SOLICITANTE / ORIGEN | Crear pedido urgente para TALLER y COMPRAS | Dos tarjetas de destino independientes |
| 2 | OPERADOR_A / TALLER | Tomar el circuito hasta “En proceso” | Solo cambia TALLER |
| 3 | OPERADOR_B / COMPRAS | Marcar leído y tomar | Solo cambia COMPRAS |

El solicitante debe ver el resumen por destinos sin abrir cada tarjeta. Cada sector debe ver únicamente sus acciones operativas.

## Escenario 3 — Un destino resuelto y otro pendiente

1. Continuar el pedido del escenario 2.
2. OPERADOR_A resuelve TALLER.
3. Dejar COMPRAS pendiente.

Resultado esperado: estado global “En proceso”, progreso 1 de 2 resueltos y COMPRAS aún pendiente. Dashboard TALLER deja de mostrar el trabajo como activo; COMPRAS conserva el pendiente.

## Escenario 4 — Rechazo

1. SOLICITANTE crea un pedido para TALLER.
2. OPERADOR_A elige “Rechazar”, escribe un motivo y confirma.

Resultado esperado: destino y pedido global rechazados, motivo visible en timeline, sin acciones posteriores sobre el destino. Dashboard, bandeja y “Mis pedidos” se actualizan.

## Escenario 5 — Derivación

1. Crear pedido para TALLER.
2. OPERADOR_A selecciona “Derivar”, elige COMPRAS e informa el motivo.

Resultado esperado: TALLER conserva su destino original y aparece un nuevo destino COMPRAS pendiente. El timeline muestra sector origen, nuevo sector y motivo. COMPRAS lo recibe en su bandeja.

## Escenario 6 — Cancelación

1. SOLICITANTE crea un pedido pendiente.
2. Desde el detalle selecciona “Cancelar pedido”, informa motivo y confirma.

Resultado esperado: estado global cancelado, movimiento de cancelación visible y ausencia de acciones operativas posteriores. Verificar actualización en dashboard, bandeja y “Mis pedidos”.

## Escenario 7 — SLA vencido

1. Configurar en ambiente de prueba una regla corta para TALLER.
2. Crear un pedido y esperar hasta superar el límite sin completar el hito.
3. Actualizar el dashboard.

Resultado esperado: el pedido encabeza urgencias, muestra texto “Vencido”, indicador rojo y tiempo excedido. Debe aparecer en el filtro “SLA vencido”. Al completar el hito, el movimiento debe conservar el resultado histórico incumplido.

## Escenario 8 — Usuario sin membresía

1. Ingresar como SIN_MEMBRESIA.
2. Intentar seleccionar TALLER mediante un ID persistido de una sesión anterior.
3. Navegar al dashboard del módulo.

Resultado esperado: `/mis-sectores/` no devuelve TALLER, se descarta el ID persistido y se muestra selección vacía o mensaje de falta de sectores. El usuario no puede operar destinos aunque sea staff sin membresía. No debe existir un bucle entre login, selección y dashboard.

## Control final

- No hubo recarga completa del navegador.
- Cada mutation mostró toast y actualizó las cuatro vistas relacionadas.
- Las acciones visibles coincidieron exactamente con `acciones_permitidas`.
- Los errores 400/403 mostraron el mensaje del backend sin trazas.
- El detalle inexistente mostró un estado 404 comprensible.
- Al cerrar sesión e ingresar con otro usuario, el sector anterior no fue heredado.
