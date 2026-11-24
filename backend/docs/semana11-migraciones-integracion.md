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

## Pendientes

- Quedan 13 lecturas repetidas: `reservas.ajustar_reserva` vuelve a bloquear los
  repuestos y a leer lo comprometido que `disponibilidad.evaluar` ya leyó. Unificarlo
  cambia la forma de calcular faltantes; conviene acordarlo antes.
- Hallazgo para la tarea bloqueada de Bastián: los índices GIN de búsqueda de MS3
  (`ix_*_trgm`, `0006_ms3`) existen en la migración pero no en el modelo, por lo que
  `alembic revision --autogenerate` propondría borrarlos.
