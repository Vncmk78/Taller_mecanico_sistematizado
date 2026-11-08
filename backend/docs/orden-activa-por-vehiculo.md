# Una sola orden activa por vehículo

Decisión de negocio aprobada por Martín para el Bloque 3 el 7 de noviembre de
2026. La sistematización 4.7-4.9 define los ingresos físicos, estados terminales
y nuevas atenciones, pero no fijaba esta unicidad. Esta decisión complementa
esa definición; no cambia el catálogo de ocho estados.

## Regla y API

Activa: cualquier estado distinto de Entregado (7) y Cancelado (8). Solo puede
existir una por vehículo, tenga o no mecánico. `POST /api/ordenes`, solo para
Administrador, responde `409` con `{"detail": "El vehículo ya tiene una orden
activa (n° X)"}` si existe otra. No crea ingreso, orden, historial, outbox ni
auditoría de cupo. No cambian el body, la respuesta `201` ni los otros rechazos.

El núcleo `registrar_orden_sin_confirmar()` bloquea el vehículo y comprueba la
regla antes del ingreso y del cupo. La futura creación desde una solicitud
deberá llamar a ese mismo núcleo y heredar el rechazo; ese endpoint sigue
pendiente. El wrapper confirma o revierte la operación completa.

## Base y migración

El índice único parcial `uq_orden_activa_por_vehiculo` sobre `vehiculo_id`,
con condición `estado_codigo NOT IN (7, 8)`, respalda el servicio. También se
declara en el modelo para las pruebas SQLite y para que coincida con Alembic.

La migración `0013_orden_activa_ms2`, desde `0012_integracion_ms2`, bloquea las
escrituras de órdenes mientras comprueba y crea el índice. Si hay duplicados,
aborta con los vehículos y las órdenes implicadas. No borra ni cancela órdenes,
no modifica ingresos y no inventa fechas históricas. El downgrade solo retira
el índice; no elimina filas.

Antes de aplicarla a un ambiente existente, ejecutar solo lectura:

```sql
SELECT vehiculo_id, array_agg(orden_id ORDER BY orden_id) AS ordenes, count(*)
FROM orden_trabajo WHERE estado_codigo NOT IN (7, 8)
GROUP BY vehiculo_id HAVING count(*) > 1;
```

Presentar el diagnóstico y acordar qué hacer con esos datos antes de migrar.
Para verificar desde cero, usar bases desechables y las migraciones existentes.
No reinicializar una base compartida ni aplicar correcciones automáticas.

## Contrato y coordinación

Es MAJOR 3.0.0 porque restringe una operación existente. Las copias 2.2.1 y
anteriores permanecen intactas. La web ya muestra el `detail` del 409; validar
esa experiencia antes del despliegue. Integración IV no consume el alta de
órdenes en su catálogo actual, pero requiere el aviso de versión y revisión
de sus recorridos. Los avisos al equipo y el despliegue no se consideran
completados por crear el contrato local.

## Pendientes distintos de esta entrega

Esta restricción por sí sola no cierra el ingreso físico. El cierre al entregar
y la devolución se incorporaron posteriormente en la Entrega A, integrada
localmente con la web y pendiente de publicación; ver
[contrato-web-bloques-3-4.md](contrato-web-bloques-3-4.md).
El alta y consulta de solicitudes están integradas localmente con la web en la
Entrega B, pendiente de publicación. La revisión y creación vinculada siguen en C. Una orden
Entregada o Cancelada deja de ocupar la unicidad; cancelar no cierra el ingreso.
