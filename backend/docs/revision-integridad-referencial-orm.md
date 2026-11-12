# Revisión de integridad referencial, índices y consultas ORM (MS1–MS4)

**Semana 9 — Revisar integridad referencial, índices y consultas ORM utilizadas por los servicios.**

Cubre los cuatro servicios. Se migró cada uno desde cero con **sus** migraciones
(`alembic upgrade head`) en una base PostgreSQL vacía y se comparó con sus
modelos ORM. Para que la revisión no se quede en el documento, quedó convertida
en la prueba `tests/test_integridad_referencial_servicios.py`.

## 1. Cómo se revisó

| Qué | Cómo |
|---|---|
| Modelo ORM = migraciones | `alembic.autogenerate.compare_metadata` contra la base migrada |
| Toda tabla tiene PK | `pg_constraint` (`contype = 'p'`) |
| Toda FK tiene índice | Hay un índice cuyas primeras columnas son las de la FK (`pg_index.indkey`) |
| ON DELETE explícito y coherente | `confdeltype` en la base = `ondelete` del modelo |
| Sin FK entre servicios | Toda tabla referida es del mismo servicio |
| Carga de relaciones ORM | `relationship.lazy` de cada mapper y conteo de SQL por endpoint (MS3) |

Para correrla se necesita un PostgreSQL local donde se puedan crear bases:

```bash
export INTEGRIDAD_PG_ADMIN_URL=postgresql+psycopg://taller:taller@localhost:5432/postgres
python -m pytest tests/test_integridad_referencial_servicios.py -v
```

Crea y borra bases `verificar_integridad_<servicio>_<id>`. Sin la variable, la
prueba se salta.

## 2. Resultado por servicio

| Servicio | Tablas | FK | FK sin índice | ON DELETE | Modelo = migración |
|---|---|---|---|---|---|
| MS1 Auth | 5 | 7 | 4 (aceptadas, ver §3) | todas explícitas | ✔ |
| MS2 Taller | 17 | 15 | 3 (aceptadas, ver §3) | todas explícitas | ✘ `ix_orden_mecanico_estado` |
| MS3 Presupuestos | 10 | 11 | 0 | todas explícitas | ✔ (salvo índices GIN, §4) |
| MS4 Evidencias | 1 | 0 | — | — | ✔ |

- Todas las tablas tienen PK.
- No hay FK entre servicios: las relaciones entre servicios (orden, usuario,
  cliente) son referencias lógicas validadas por API. En MS3, además, lo verifica
  `scripts/verificar_aislamiento_ms3.py`.

### Políticas ON DELETE

| Política | Dónde | Por qué |
|---|---|---|
| `RESTRICT` | Casi todas (historiales, movimientos, órdenes, ítems → repuesto) | Auditoría: no se borra lo que tiene historia |
| `CASCADE` | `usuario_rol`, `historial_rol`, `notificacion` → usuario; `vehiculo` → cliente; `item_presupuesto` → versión; `historial_proveedor_repuesto` → repuesto | Son parte del padre y no tienen sentido sin él |
| `SET NULL` | `usuario_rol.asignado_por_id`, `historial_rol.responsable_id` | Si se borra el usuario que asignó, la asignación se conserva |

En MS3 los `CASCADE` no se ejecutan en la práctica. Una versión enviada o
aprobada no se puede borrar (triggers 0003), y un repuesto con historia tampoco
(lo impide `catalogo.eliminar_repuesto`).

## 3. Claves foráneas sin índice

Sin índice, borrar o actualizar el padre obliga a PostgreSQL a recorrer la
tabla hija entera para revisar la FK, y los JOIN por esa columna no tienen
índice.

| FK | Servicio | Decisión |
|---|---|---|
| `usuario_rol.rol_id` → rol | MS1 | Aceptada. `rol` tiene 3 filas fijas y nunca se borra. Si se lista "usuarios por rol" (mecánicos para asignar), conviene un índice `(rol_id, usuario_id)`. **Propuesta** |
| `historial_rol.rol_id` → rol | MS1 | Aceptada (mismo motivo) |
| `usuario_rol.asignado_por_id`, `historial_rol.responsable_id` → usuario | MS1 | Aceptadas: solo se recorren al borrar un usuario, y la API no borra usuarios físicamente |
| `historial_estado.estado_anterior/estado_nuevo` → estado_orden | MS2 | Aceptadas: catálogo fijo de 8 estados |
| `historial_validacion_cupo_ingreso.ingreso_id` → ingreso_vehiculo | MS2 | Aceptada por ahora (auditoría que se consulta por vehículo). **Propuesta:** índice si se consulta por ingreso |

La prueba compara contra esta lista exacta. Una FK nueva sin índice la hace
fallar: hay que agregar el índice en la migración o documentar aquí por qué no.

## 4. Diferencias entre modelo y migración

| Servicio | Diferencia | Decisión |
|---|---|---|
| MS2 | `ix_orden_mecanico_estado (mecanico_actual_id, estado_codigo)` lo crea `0008_ms2`, pero `OrdenTrabajo` no lo declara. Un `create_all` (pruebas con SQLite) no lo crea, y un `alembic revision --autogenerate` propondría **borrarlo** | **Corregir** en el modelo (tarea "Corregir mapeos ORM…") |
| MS3 | `ix_repuesto_nombre_trgm`, `ix_proveedor_nombre_trgm`, `ix_proveedor_contacto_trgm` (GIN `pg_trgm` sobre `ms3_normalizar(...)`) existen solo en `0006_ms3` | Aceptada: dependen de una función y una extensión de PostgreSQL. El modelo también se usa con SQLite en las pruebas de integración |

## 5. Consultas ORM (MS3)

Estrategia de carga de cada relación de MS3 y lo que se encontró midiendo las
consultas SQL de cada endpoint (500.000 movimientos, 20.000 repuestos, 20.000
presupuestos):

| Relación | Carga | Hallazgo |
|---|---|---|
| `Presupuesto.versiones`, `VersionPresupuesto.items/decision` | `selectin` | Bien: una consulta por nivel |
| `ItemPresupuesto.repuesto` | `select` (perezosa) | **N+1**: una consulta por ítem al armar el detalle |
| `Repuesto.proveedor` | `select` (perezosa) | **N+1**: una consulta por repuesto en listados, alertas, faltantes y reservas (`GET /repuestos` = 48 consultas para 50 filas) |
| `Proveedor.repuestos` | `selectin` | **Carga de más**: leer el proveedor de UN repuesto traía todos los repuestos de ese proveedor |
| `HistorialProveedorRepuesto.proveedor_*` | `joined` | Bien |
| `MovimientoInventario.fecha_hora` | `server_default now()` | Un `refresh` después de cada INSERT hacía un SELECT por movimiento (aprobar 10 repuestos = 10 SELECT de más) |

Límite transaccional: los routers leían el presupuesto (eso abre una
transacción) y después llamaban a MS2 por HTTP. La conexión quedaba
*idle in transaction* mientras MS2 respondía, y MS2 vuelve a consultar a MS3
para verificar decisiones y envíos.

Se corrige en "Corregir mapeos ORM y límites transaccionales detectados durante
las pruebas". Las consultas lentas y los índices propuestos están en
`docs/consultas-lentas-y-ajustes-indices.md`.
