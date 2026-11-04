# Consultas innecesarias o lentas y ajustes de índices (MS3)

**Semana 9 — Identificar consultas innecesarias o lentas y proponer ajustes de índices.**

Sigue a `docs/revision-integridad-referencial-orm.md` (hallazgos) y a
`docs/revision-indices-inventario.md` (índices de inventario, 0008_ms3).

## 1. Cómo se midió

- Una base PostgreSQL 16 de prueba con volumen de un taller con años de uso:
  300 proveedores, 20.000 repuestos, 500.000 movimientos, 20.000 presupuestos
  (60.000 versiones, 300.000 ítems), con `VACUUM ANALYZE`.
- Cada endpoint se llamó con la app real (sesión normal, sin la transacción de
  pruebas). Se capturó cada `SELECT` que mandó SQLAlchemy y se ejecutó con
  `EXPLAIN (ANALYZE, BUFFERS)` con sus mismos parámetros.
- "Antes" = Develop al inicio de la semana 9. "Después" = con las correcciones
  de mapeos ORM y el índice `0010_ms3`.

Cada consulta es un viaje de ida y vuelta a la base. En producción (Vercel →
Neon) ese viaje pesa más que la ejecución misma, así que **sobran consultas**
es tan importante como **consultas lentas**.

## 2. Resultado

| Endpoint | Consultas antes | Consultas después | ms en la base antes | ms después |
|---|---:|---:|---:|---:|
| `GET /repuestos` (página de 50) | 48 | 4 | 3,2 | 2,3 |
| `GET /repuestos?texto=` | 48 | 4 | 5,0 | 2,2 |
| `GET /repuestos?solo_bajo_umbral` | 48 | 4 | 5,6 | 3,8 |
| `GET /inventario/alertas` | 31 | 3 | 1,8 | 2,1 |
| `GET /inventario/movimientos` (sin filtro) | 2 | 2 | **156,4** | 44,2 |
| `GET /presupuestos/{id}` | 12 | 6 | 0,2 | 0,2 |
| `GET /inventario/ordenes/{id}/disponibilidad` | 11 | 10 | 0,5 | 0,3 |
| `GET /proveedores` | 3 | 3 | 1,0 | 1,4 |
| `GET /inventario/movimientos?repuesto_id` / `?orden_id` | 2 | 2 | 0,1 | 0,1 |
| `GET /inventario/stock/{id}` | 4 | 4 | 0,1 | 0,1 |
| `GET /presupuestos` (página) | 5 | 5 | 2,8 | 2,5 |
| `GET /presupuestos?orden_id` (cliente) | 5 | 5 | 0,1 | 0,1 |
| `GET /repuestos/{id}/trazabilidad` | 8 | 8 | 0,3 | 0,3 |
| `GET /proveedores/{id}/trazabilidad` | 4 | 4 | 1,5 | 1,6 |

Escrituras, medidas con las pruebas (10 repuestos en el presupuesto):

| Operación | Antes | Después |
|---|---|---|
| Aprobar (reserva 10 repuestos) | 67 sentencias, entre ellas 10 `SELECT proveedor` y 10 `SELECT fecha_hora` | 52, sin ninguna de esas |
| Crear modificación | 36 | 24 |
| Reemplazar 10 ítems | 38 | 27 |

## 3. Consultas innecesarias encontradas (corregidas)

| # | Dónde | Problema | Corrección |
|---|---|---|---|
| 1 | Listado de repuestos, alertas, faltantes, reservas | `Repuesto.proveedor` perezosa: 1 consulta por repuesto (N+1) | `lazy="selectin"`: 1 consulta por lote |
| 2 | Detalle del presupuesto | `ItemPresupuesto.repuesto` perezosa: 1 consulta por ítem | `lazy="selectin"` |
| 3 | Cualquier lectura de `repuesto.proveedor` | `Proveedor.repuestos` en `selectin` traía todos los repuestos del proveedor | Perezosa; el listado de proveedores la pide con `selectinload` |
| 4 | Listado de presupuestos | Con (2) habría cargado repuestos que el resumen no usa | `lazyload(ItemPresupuesto.repuesto)` en ese listado |
| 5 | Cada movimiento | `refresh` después del INSERT para leer `fecha_hora` | La fecha llega con `RETURNING` (`eager_defaults`) |

`services/ms3_presupuestos/tests/test_consultas_por_endpoint.py` fija estos
números. Para cada endpoint mide con 2 y con 8 filas: deben dar lo mismo (sin
N+1) y no superar el presupuesto medido.

## 4. Consulta lenta encontrada y ajuste de índice (aplicado)

`GET /inventario/movimientos` sin filtros (el historial de la vista de
inventario) ordena por `fecha_hora DESC, movimiento_id DESC` y pagina. Ningún
índice empezaba por `fecha_hora`, así que PostgreSQL leía y ordenaba los
500.000 movimientos para devolver 50:

```
Limit → Gather Merge → Sort → Parallel Seq Scan on movimiento_inventario   ~118 ms
```

**Migración `0010_ms3`:** `ix_movimiento_inventario_fecha (fecha_hora DESC, movimiento_id DESC)`.

```
Limit → Index Scan using ix_movimiento_inventario_fecha                    <1 ms
```

Lo verifica `test_indices_inventario.py`: usa el índice y no ordena en memoria.

## 5. Propuestas que no se aplicaron

| # | Propuesta | Por qué no ahora |
|---|---|---|
| P1 | El `count(*)` de la paginación de movimientos sin filtros recorre la tabla (~40 ms con 500.000 filas) | Es exacto y hoy es aceptable. Si crece: devolver `hay_mas` en vez del total, o usar `pg_class.reltuples` como estimación |
| P2 | MS1: índice `(rol_id, usuario_id)` en `usuario_rol` para listar usuarios por rol (mecánicos para asignar) | Es otro servicio; `rol` tiene 3 filas y hoy no hay volumen. Se propone a quien lo mantiene |
| P3 | MS2: índice en `historial_validacion_cupo_ingreso.ingreso_id` | Ídem; hoy esa auditoría se consulta por vehículo |
| P4 | `GET /proveedores/{id}/trazabilidad` filtra con `proveedor_anterior_id = X OR proveedor_nuevo_id = X` (seq scan, 1,5 ms) | Ambas columnas tienen índice. Con más historial, reescribir como `UNION ALL` para usar los dos |
| P5 | Aprobar un presupuesto lee el grafo del presupuesto 3 veces (lectura, `FOR UPDATE` con `populate_existing`, versión) | Volver a leer después del bloqueo es intencional (datos frescos). Se puede ahorrar una lectura pasando la versión ya bloqueada |

## 6. Cómo se repite la medición

```bash
# índices: plan real de cada consulta del repositorio
python -m pytest services/ms3_presupuestos/tests/test_indices_inventario.py
# consultas por endpoint (sin N+1, dentro del presupuesto)
python -m pytest services/ms3_presupuestos/tests/test_consultas_por_endpoint.py
```
