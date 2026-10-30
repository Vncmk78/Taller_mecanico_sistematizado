# Revisión de índices y consultas de inventario y trazabilidad (MS3)

Semana 7 · *Revisar índices y consultas utilizadas por inventario y trazabilidad*.
Resultado: migración `0008_ms3`, consulta de saldo en lote y pruebas
`services/ms3_presupuestos/tests/test_indices_inventario.py`.

## 1. Cómo se midió

- Base PostgreSQL 16 migrada a `0007_ms3` con 200 proveedores, 5.000 repuestos y
  **460.000 movimientos**.
- Uno de los repuestos es "muy usado", con 63.000 movimientos (como un aceite
  que entra y sale todos los días), y un proveedor tiene 15.000 ingresos.
- `EXPLAIN (ANALYZE)` de la misma SQL que generan los repositorios, antes y
  después de `0008_ms3`.

## 2. Consultas revisadas

| # | Consulta (dónde) | Se usa en |
|---|---|---|
| Q1 | Saldo reservado por orden de un repuesto (`comprometido_por_orden`) | **Cada** movimiento de stock, validación de disponibilidad, reserva al aprobar, stock |
| Q2 | Movimientos de un repuesto, más recientes primero, página de 50 | `GET /inventario/movimientos?repuesto_id=` |
| Q3 | Movimientos de una orden, más recientes primero | `GET /inventario/movimientos?orden_id=`, liberación |
| Q4 | Ingresos de un proveedor, más recientes primero | `GET /inventario/movimientos?proveedor_id=` |
| Q5 | Consumido por orden y repuesto | Disponibilidad de la orden, reserva de modificaciones |
| Q6 | Unidades entregadas por un proveedor, por repuesto | `GET /proveedores/{id}/trazabilidad` |
| Q7 | Ingresos de un repuesto agrupados por proveedor | `GET /repuestos/{id}/trazabilidad` |
| Q8 | Saldo reservado de varios repuestos | Validar/reservar/descontar varios repuestos |

## 3. Hallazgos (antes)

Los índices eran de una sola columna: `ix_movimiento_inventario_repuesto_id`,
`ix_movimiento_inventario_orden_id` e `ix_movimiento_inventario_proveedor_id`.
Con eso se encuentran las filas, pero:

1. **Todas las consultas ordenadas ordenaban en memoria.** Para la página de 50
   movimientos del repuesto muy usado, PostgreSQL leía y ordenaba sus 63.000 filas
   (Q2: 16 ms). Lo mismo pasaba con Q4 para un proveedor grande.
2. **Q1 se ejecuta en cada operación de stock** y leía las filas de la tabla
   (no solo del índice), además de ordenarlas: 37 ms en el repuesto muy usado.
3. **Consultas N+1:** validar o reservar N repuestos hacía N consultas de saldo,
   una por repuesto.
4. **Q7 filtraba `tipo = 'ingreso'` después de leer el repuesto completo:**
   63.000 filas leídas para quedarse con 15.000.
5. Q3 y Q5 estaban bien: una orden tiene pocos movimientos.

## 4. Cambios

| Índice nuevo (`0008_ms3`) | Columnas | Sirve a |
|---|---|---|
| `ix_movimiento_inventario_saldo` | `(repuesto_id, movimiento_id) INCLUDE (orden_id, tipo, cantidad) WHERE orden_id IS NOT NULL` | Q1, Q8: lectura **solo del índice** y ya en orden |
| `ix_movimiento_inventario_repuesto_fecha` | `(repuesto_id, fecha_hora DESC, movimiento_id DESC)` | Q2 (reemplaza `*_repuesto_id`; también cubre la FK) |
| `ix_movimiento_inventario_orden_fecha` | `(orden_id, fecha_hora DESC, movimiento_id DESC) WHERE orden_id IS NOT NULL` | Q3, Q5 (reemplaza `*_orden_id`) |
| `ix_movimiento_inventario_proveedor_fecha` | `(proveedor_id, fecha_hora DESC, movimiento_id DESC) INCLUDE (repuesto_id, cantidad) WHERE proveedor_id IS NOT NULL` | Q4, Q6 (reemplaza `*_proveedor_id`; también cubre la FK) |
| `ix_movimiento_inventario_ingresos` | `(repuesto_id, proveedor_id) INCLUDE (cantidad, fecha_hora) WHERE tipo = 'ingreso'` | Q7 |

- Se eliminaron los tres índices de una columna, porque los compuestos los
  cubren (misma primera columna). No quedan índices duplicados que cobren en
  cada `INSERT`.
- **Consulta en lote:** `RepositorioMovimientos.comprometido_por_ordenes(ids)`
  calcula el saldo de N repuestos en **una** consulta (Q8). La usan la
  validación de disponibilidad, la reserva al aprobar, el descuento de varios
  repuestos y la liberación de una orden.

## 5. Resultado

| # | Antes | Después | Plan después |
|---|---|---|---|
| Q1 | 37,3 ms | 9,3 ms | Index Only Scan `*_saldo`, sin ordenar |
| Q2 | 16,1 ms | 0,13 ms | Index Scan `*_repuesto_fecha`, lee solo 50 filas |
| Q3 | 0,75 ms | 0,06 ms | Index Scan `*_orden_fecha` |
| Q4 | 7,5 ms | 0,05 ms | Index Scan `*_proveedor_fecha`, lee solo 50 filas |
| Q5 | 0,5 ms | 0,8 ms | Índice `*_orden_fecha` (sin cambio relevante) |
| Q6 | 6,5 ms | 4,1 ms | Index Only Scan `*_proveedor_fecha` |
| Q7 | 13,2 ms | 3,4 ms | Index Only Scan `*_ingresos` |
| Q8 (50 repuestos) | 4,2 ms | 0,75 ms | Index Only Scan `*_saldo` |

Con 460.000 movimientos, los cinco índices nuevos ocupan unos 56 MB (83 MB
contando la PK y la clave única), y la tabla unos 39 MB. Es un costo aceptable: es una tabla que
casi solo recibe `INSERT`, y se consulta en cada operación de stock.

## 6. Lo que queda (no se hizo en esta tarea)

- **Q1 sigue siendo proporcional al historial reservado del repuesto.** El saldo
  por orden se calcula recorriendo los movimientos en orden, porque un consumo
  mayor que la reserva no deja deuda. Si el historial llega a cientos de miles
  de movimientos por repuesto, conviene una tabla de saldos
  `reserva_orden(repuesto_id, orden_id, reservado)` actualizada en la misma
  transacción de cada movimiento.
- **Alertas de stock bajo:** `stock < coalesce(umbral_particular, :general)` no
  se puede indexar con un parámetro. Con 5.000 repuestos recorre la tabla en
  menos de 1 ms. Solo valdría la pena con muchos más repuestos.

## 7. Cómo se verifica

`test_indices_inventario.py` hace `EXPLAIN` de cada consulta real con
`enable_seqscan` y `enable_bitmapscan` desactivados, y comprueba:

- que cada consulta usa su índice;
- que los listados y el saldo no ordenan en memoria;
- que el saldo se lee solo del índice;
- que los índices reemplazados ya no existen;
- que el saldo de varios repuestos sale en una sola consulta.
