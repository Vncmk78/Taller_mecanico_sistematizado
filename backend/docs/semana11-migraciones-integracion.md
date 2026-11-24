# Semana 11 — Consultas duplicadas y pruebas de regresión

Responsable: Martín López · 2026-11-19 · Rama `MartinL` (al día con `Develop` en `29c543e`).
Ambiente: PostgreSQL 16 (ambiente `sgtm_pruebas`), Python 3.13.

La tarea "Ejecutar migraciones en ambiente de integración y corregir problemas de
persistencia" está bloqueada por Bastián y queda pendiente.

## 1. Limpiar consultas duplicadas y código ORM innecesario

Con `log_statement = all` en PostgreSQL durante los recorridos E2E se contaron las
sentencias repetidas dentro de una misma transacción. Aprobar un presupuesto leía la
versión con sus ítems, repuestos y proveedores **3 veces** y lo consumido por la orden
**2 veces**.

Cambios en `services/ms3_presupuestos/services/presupuestos.py`:

- `decidir_version` y `enviar_version` toman la versión de las ya cargadas con el
  presupuesto (`_version_de`) en vez de pedirla otra vez.
- `_pendientes` se calcula una vez y sirve para evaluar la disponibilidad y para reservar.
- `refresh` relee solo la columna que escribe el servidor (`bloqueada_en`, `enviado_en`),
  no la versión con todas sus relaciones.

| Mismo recorrido E2E (61 pasos), MS3 | Antes | Después |
|---|---|---|
| Sentencias SQL | 251 | 207 (−18 %) |
| Sentencias repetidas en la misma transacción | 44 | 13 (−70 %) |

## 2. Agregar pruebas de regresión para los defectos corregidos

| Prueba | Qué protege | Con el código anterior |
|---|---|---|
| `services/ms3_presupuestos/tests/test_consultas_decision.py` (4) | Aprobar, rechazar y enviar leen la versión **una** vez y lo consumido **una** vez; `bloqueada_en` y `enviado_en` siguen viniendo del servidor | 3 de 4 fallan (3 lecturas de la versión, 2 de lo consumido) |

Comando: `python scripts/verificar_backend.py services/ms3_presupuestos/tests`

## 3. SCRUM-649 — Corregir defectos ORM encontrados en las pruebas de integración

Se corrigieron tres defectos vistos al correr la suite con PostgreSQL real
(`python scripts/verificar_backend.py`): dos de sesión / modelo ORM y uno de la
prueba de drift, que ocultaba errores de migración. Los de migración quedan para la
tarea de migraciones (ver Pendientes).

**Una sola lectura de los repuestos bloqueados al aprobar** (las 13 lecturas repetidas que quedaban). Nuevo
`disponibilidad.bloquear_y_leer_compromisos(uow, ids)`: bloquea los repuestos
(`FOR UPDATE`) y lee lo comprometido una vez. `decidir_version` pasa ese resultado a
`evaluar(..., bloqueo=)` y a `reservas.ajustar_reserva(..., bloqueo=)`. Ambos
parámetros son opcionales y solo por nombre: sin ellos, las funciones hacen lo mismo
que antes (las usan `reservar_presupuesto_aprobado`, la API de inventario y las
pruebas). No cambia el cálculo: `evaluar` marca faltante si
`pendiente > stock − comprometido_otras`, y `ajustar_reserva` si
`quiero − tengo > stock − (tengo + otras)`, que es la misma condición. Con las filas
bloqueadas y sin escrituras entre medio, la segunda lectura no podía dar otro resultado.

| Aprobar un presupuesto con 2 repuestos | Antes | Después |
|---|---|---|
| `SELECT repuesto ... FOR UPDATE` | 2 | 1 |
| Lectura de lo comprometido | 2 | 1 |
| `SELECT proveedor` | 4 | 3 |

La lectura de proveedor que queda bajo el `FOR UPDATE` es intencional:
`populate_existing` refresca la fila bloqueada. Quitarla obligaría a cambiar
`bloquear_varios`, que usan otros flujos, y podría volver el N+1 que el selectin evitó.

**SAWarning en las pruebas de persistencia.** Las dos pruebas construyen el
movimiento con `repuesto_id=` en vez de `repuesto=`. Además, el `conftest.py` de MS3
convierte toda `SAWarning` en error, así que la próxima falla de la prueba en vez de
pasar inadvertida.

**Salida de Alembic ilegible en la prueba de drift** (`UnicodeDecodeError` en Windows). Nuevo helper `_alembic()`
en `tests/test_integridad_referencial_servicios.py`: fija `PYTHONIOENCODING=utf-8`
en el proceso hijo y decodifica en UTF-8 con `errors="replace"`.

| Prueba de regresión | Qué protege | Con el código anterior |
|---|---|---|
| `services/ms3_presupuestos/tests/test_consultas_reserva.py` (4) | Aprobar bloquea y lee lo comprometido **una** vez; los faltantes, las reservas y lo comprometido por otras órdenes no cambian; `ajustar_reserva` sin `bloqueo` sigue funcionando | Falla `test_aprobar_con_stock_...` (2 bloqueos, 2 lecturas) |
| `services/ms3_presupuestos/tests/conftest.py` (SAWarning = error) + `test_persistencia_orm.py` | Ninguna prueba de MS3 deja objetos fuera de la sesión | Fallan `test_clave_de_operacion_repetida_es_rechazada` y `test_consumo_sin_orden_es_rechazado` |
| `tests/test_integridad_referencial_servicios.py::test_la_salida_de_alembic_se_lee_completa_con_tildes` | La salida de Alembic llega completa (con tildes) | Falla: `TypeError: argument of type 'NoneType'` (el hilo lector murió) |

Suite completa: `python scripts/verificar_backend.py` → **2981 passed, 56 warnings**
(antes 2976 passed, 59 warnings; ya no quedan advertencias de persistencia).

## Pendientes

- Para la tarea de migraciones: `alembic downgrade base` de MS2 falla con
  `constraint "ck_cliente_ck_cliente_usuario_id_positivo" does not exist`. En el
  `downgrade()` de `0002_restricciones_ms2.py` (líneas 71-74), usar los nombres sin
  prefijo (`"usuario_id_positivo"`) o `op.f("ck_cliente_usuario_id_positivo")`.
- Tarea bloqueada de Bastián: los índices GIN de búsqueda de MS3
  (`ix_*_trgm`, `0006_ms3`) existen en la migración pero no en el modelo, por lo que
  `alembic revision --autogenerate` propondría borrarlos.
