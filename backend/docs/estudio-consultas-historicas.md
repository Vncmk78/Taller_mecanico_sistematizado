# Consultas históricas, paginación y filtros por vehículo

Semana 8 · SCRUM-520 / SCRUM-704

## Alcance y fuentes

El historial permite reconstruir las atenciones de un vehículo sin reabrir ni
borrar órdenes terminales. La sistematización final, secciones 4.2, 4.8 y 4.9,
separa cada atención de sus antecedentes: una nueva atención tiene otra orden
y conserva la anterior. Este estudio describe la consulta ya implementada;
no incorpora una nueva regla de negocio ni un catálogo de servicios.

Fuentes del repositorio:

- `services/ms2_taller/services/ordenes.py`: `listar_historial_ordenes_vehiculo`
  y `_filtro_visibilidad`.
- `services/ms2_taller/routers/ordenes.py`: validación de parámetros y errores.
- `services/ms2_taller/models/orden_trabajo.py` y migración `0003_ms2`:
  relaciones e índices.
- [Contrato de la Gateway](contratos-api-gateway.md):
  `GET /api/ordenes/vehiculo/{vehiculo_id}/historial`.

## Historial de atenciones e historial de estados

Son consultas diferentes. El historial por vehículo devuelve órdenes, con su
estado actual y fechas; incluye órdenes abiertas, entregadas y canceladas.
No limita el resultado a trabajos terminados. El detalle de una orden enlaza
con su historial de cambios de estado, que se consulta por
`GET /api/ordenes/{orden_id}/historial`, en orden cronológico ascendente.

El panel `frontend/src/presentation/components/orders/VehicleOrderHistoryPanel.tsx`
consume páginas de veinte órdenes desde el servicio HTTP compartido. Los
portales de Cliente, Mecánico y Administrador reutilizan el mismo panel y
configuran la ruta al detalle correspondiente a su portal.

## Consulta y autorización antes de paginar

1. La Gateway y MS2 validan el JWT. MS2 obtiene la identidad y roles del token.
2. MS2 comprueba que el vehículo exista y sea visible para ese usuario.
3. Filtra `OrdenTrabajo.vehiculo_id` por el vehículo solicitado y aplica el
   alcance de las órdenes. Tanto el conteo como la página usan ese filtro.
4. Calcula `total` y obtiene la página con el mismo orden estable.

| Rol | Alcance de la consulta |
| --- | --- |
| Administrador | Todas las órdenes del vehículo existente. |
| Cliente | Órdenes de vehículos cuyo cliente tiene su `usuario_id`. |
| Mecánico | Solo órdenes cuyo `mecanico_actual_id` es el usuario autenticado; el vehículo debe tener una asignación visible. |
| Cuenta con varios roles | Unión de los alcances; Administrador conserva visibilidad global. |

La propiedad se resuelve con Cliente y Vehículo en la base de MS2. La identidad
de MS1 es una referencia lógica; no se consulta su base ni se crea una FK entre
microservicios. Un vehículo ajeno y uno inexistente responden el mismo `404`.
Un vehículo propio sin órdenes responde `200`, `items: []` y `total: 0`.

No basta con filtrar el panel: hacerlo después de paginar podría devolver
totales ajenos, páginas incompletas o datos que el usuario no puede consultar.

## Paginación y orden estable

El contrato usa `limit` (predeterminado 20, mínimo 1, máximo 100) y `offset`
(predeterminado 0, mínimo 0). `vehiculo_id` debe ser positivo. La respuesta es
`{items, total, limit, offset}`; los parámetros inválidos responden `422`.

La consulta ordena por `creado_en DESC, orden_id DESC`. El identificador único
desempata cuando varias órdenes tienen la misma fecha. Por ejemplo, con tres
órdenes de la misma fecha y IDs 10, 11 y 12, `limit=2&offset=0` devuelve 12 y 11;
`limit=2&offset=2` devuelve 10.

Se conserva `LIMIT/OFFSET` porque ya está publicado y permite los controles
Anterior/Siguiente y el total. La alternativa es un cursor sobre
`(creado_en, orden_id)`, útil si el historial crece mucho, pero requeriría acordar
otro contrato con los consumidores. No se cambia por preferencia técnica.

Un orden estable no crea una instantánea entre peticiones: una inserción o
reasignación entre páginas puede desplazar resultados. El conteo y la página
también son consultas separadas y no prometen una instantánea común bajo toda
configuración de aislamiento. No hay una garantía de exportación histórica
inmutable en este endpoint.

## Filtros y costos

El filtro funcional publicado es el vehículo en la ruta; la autorización agrega
el alcance de propiedad/asignación. No se anuncian filtros por fecha, patente,
texto o estado que este endpoint no admite. El detalle de vehículo proporciona
su ID, por lo que el panel no necesita descargar todas las órdenes del taller.

La migración `0003_ms2` crea índices individuales para `vehiculo_id`,
`mecanico_actual_id` y `estado_codigo` de `orden_trabajo`. El índice
`ix_historial_estado_orden_fecha` sirve al historial de estados; no sustituye
un índice para ordenar atenciones por vehículo.

No se crea una migración adicional: no hay una medición que la justifique.
Si aparece lentitud, corresponde medir en PostgreSQL con datos representativos
y `EXPLAIN (ANALYZE, BUFFERS)`, evaluando el conteo, el ordenamiento, los offsets
grandes y las cargas ORM. El modelo usa carga `selectin` para historiales y
asignaciones, por lo que hay consultas adicionales y `limit` no equivale a un
límite de filas relacionadas cargadas. Un posible índice compuesto por vehículo,
fecha e ID debe evaluarse con esas mediciones antes de introducirlo. Este estudio
no afirma haber ejecutado un plan ni un benchmark de PostgreSQL.

## Errores y verificación

El contrato distingue `401` (JWT), `404` (vehículo no visible), `422`
(parámetros), `500` (persistencia) y `502` (MS2 no disponible desde la Gateway).
El servicio traduce los errores SQLAlchemy y hace rollback; no expone SQL al
consumidor.

Las pruebas existentes en `tests/test_ordenes_api.py` verifican paginación y
desempate, propiedad, resultado vacío, alcance del mecánico y parámetros fuera
de rango. Las pruebas de `VehicleOrderHistoryPanel.test.tsx` verifican el cambio
de página y el enlace al detalle. Su ejecución valida comportamiento en bases
aisladas y componentes; no sustituye una prueba de carga o concurrencia en
PostgreSQL.
