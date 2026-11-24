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

## 3. SCRUM-651 — Reproducir y clasificar errores de persistencia

Fecha: 2026-11-24. Ambiente `sgtm_pruebas` (PostgreSQL 16 ×4 + MinIO), Python 3.14.

Cómo se reprodujo (desde `backend/`):

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/ambiente_pruebas.py infra
python scripts/verificar_backend.py               # suite completa con PostgreSQL real
python scripts/diagnosticar_migraciones.py        # heads, drift, check, downgrade/upgrade (MS1-MS4)
```

Resultado de la suite: **2976 passed, 59 warnings** (5 min). De las advertencias,
2 son de persistencia; el resto son deprecaciones de Starlette/AnyIO ajenas a la
persistencia. `diagnosticar_migraciones.py` (nuevo) migra cada servicio en una base
descartable y compara modelo ↔ migraciones con `compare_type` y
`compare_server_default` (la prueba de integridad solo usa `compare_type`).

| ID | Tipo | Severidad | Error / advertencia | Archivo:línea | Cómo se reproduce |
|---|---|---|---|---|---|
| MIG-1 | Migración | Media | `downgrade base` de MS2 falla: `constraint "ck_cliente_ck_cliente_usuario_id_positivo" does not exist`. El `downgrade()` pasa el nombre ya prefijado y la convención de nombres lo vuelve a prefijar. Las líneas 72-74 tienen el mismo patrón. No afecta `upgrade`; impide revertir MS2 hasta la base. | `services/ms2_taller/alembic/versions/0002_restricciones_ms2.py:71` | `python scripts/diagnosticar_migraciones.py ms2_taller` |
| MIG-2 | Migración / modelo ORM | Media | Drift MS3: los índices GIN `ix_repuesto_nombre_trgm`, `ix_proveedor_nombre_trgm` e `ix_proveedor_contacto_trgm` existen en la migración y no en el modelo. `alembic check` falla y `revision --autogenerate` propondría borrarlos. Aceptado hoy en `DIFERENCIAS_ACEPTADAS`. **Es de la tarea bloqueada de Bastián**: no se toca. | `services/ms3_presupuestos/alembic/versions/0006_indices_busqueda_ms3.py:45` · `models/proveedor.py` | `python scripts/diagnosticar_migraciones.py ms3_presupuestos` |
| MIG-3 | Migración (herramienta de verificación) | Media | `PytestUnhandledThreadExceptionWarning`: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8d`. La prueba de drift lee la salida de `alembic upgrade` con `text=True` (cp1252 en Windows) y los títulos de las migraciones vienen en UTF-8 (`Í` = `C3 8D`). Si la migración fallara, el mensaje de error se perdería. | `tests/test_integridad_referencial_servicios.py:103` | `python scripts/verificar_backend.py tests/test_integridad_referencial_servicios.py` (ver *warnings summary*) |
| SES-1 | Sesión | Baja | `SAWarning: Object of type <MovimientoInventario> not in session, add operation along 'Repuesto.movimientos' will not proceed`. El movimiento se construye con `repuesto=...` antes del `begin_nested()`; el backref lo mete en la colección, pero en SQLAlchemy 2.0 no entra a la sesión (sin `cascade_backrefs`) y el autoflush lo ignora. El código de producción no lo hace (construye y agrega en la misma línea), pero la advertencia pasaba inadvertida. | `services/ms3_presupuestos/tests/test_persistencia_orm.py:110` y `:116` | `python scripts/verificar_backend.py services/ms3_presupuestos/tests/test_persistencia_orm.py` (ver *warnings summary*) |
| SES-2 | Sesión / modelo ORM | Baja (rendimiento) | Las 13 lecturas repetidas pendientes: al aprobar, `disponibilidad.evaluar(bloquear=True)` y luego `reservas.ajustar_reserva` hacen cada uno el `SELECT ... FOR UPDATE` de los repuestos (con `populate_existing`, que relanza el selectin de proveedores) y la consulta de lo comprometido, en la misma transacción y con las filas ya bloqueadas. Medido en una aprobación con 2 repuestos: 2 bloqueos, 2 lecturas de lo comprometido, 4 de proveedores. | `services/ms3_presupuestos/services/presupuestos.py:362-368` · `services/disponibilidad.py:92,103` · `services/reservas.py:79-80` | `python scripts/verificar_backend.py services/ms3_presupuestos/tests/test_consultas_reserva.py` (prueba agregada en SCRUM-649; con el código anterior falla) |

Sin hallazgos: heads múltiples (cada servicio tiene un solo head), drift en MS1, MS2 y
MS4, errores de transacción (rollback, aislamiento, bloqueos) ni de datos en la suite.

Fuera de alcance (no son de persistencia): `StarletteDeprecationWarning` por
`HTTP_413_REQUEST_ENTITY_TOO_LARGE` / `HTTP_422_UNPROCESSABLE_ENTITY` en MS4, y el aviso de
`httpx` con `starlette.testclient`.

## 4. SCRUM-649 — Corregir defectos ORM encontrados en las pruebas de integración

Se corrigieron los hallazgos de tipo sesión / modelo ORM (SES-1, SES-2) y la
herramienta de drift (MIG-3), porque ocultaba errores de migración. MIG-1 y MIG-2
son de migración y quedan para la tarea de migraciones (ver Pendientes).

**SES-2: una sola lectura de los repuestos bloqueados al aprobar.** Nuevo
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

**SES-1: SAWarning en las pruebas de persistencia.** Las dos pruebas construyen el
movimiento con `repuesto_id=` en vez de `repuesto=`. Además, el `conftest.py` de MS3
convierte toda `SAWarning` en error, así que la próxima falla de la prueba en vez de
pasar inadvertida.

**MIG-3: salida de Alembic ilegible en la prueba de drift.** Nuevo helper `_alembic()`
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

- MIG-1 (para la tarea de migraciones): en el `downgrade()` de
  `0002_restricciones_ms2.py`, usar los nombres sin prefijo (`"usuario_id_positivo"`)
  o `op.f("ck_cliente_usuario_id_positivo")` en las líneas 71-74. Verificar con
  `python scripts/diagnosticar_migraciones.py ms2_taller`.
- MIG-2 (tarea bloqueada de Bastián): los índices GIN de búsqueda de MS3
  (`ix_*_trgm`, `0006_ms3`) existen en la migración pero no en el modelo, por lo que
  `alembic revision --autogenerate` propondría borrarlos.
