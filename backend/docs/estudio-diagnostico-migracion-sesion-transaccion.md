# Estudio: diagnóstico de errores de migración, sesión y transacción

Responsable: Martín López · 2026-11-24 · SCRUM-650.
Guía corta para diagnosticar fallas de persistencia en los cuatro servicios
(SQLAlchemy 2.0 + Alembic + PostgreSQL 16). Cada sección parte de un caso real de
este repositorio. Los comandos se ejecutan desde `backend/` con el ambiente de
pruebas levantado (`python scripts/ambiente_pruebas.py infra`).

## 1. Migraciones (Alembic)

### Primer paso: ¿en qué estado está cada base?

```powershell
python scripts/verificar_migraciones.py        # revisión actual vs head, sin modificar nada
python scripts/diagnosticar_migraciones.py     # heads, drift, check, downgrade/upgrade en bases descartables
```

### Heads múltiples

**Síntoma:** `alembic upgrade head` termina con *"Multiple head revisions are present"*.
Pasa cuando dos ramas crean una migración con el mismo `down_revision`.

**Ejemplo real:** MS2 tuvo dos ramas en paralelo: `0010_ms2 → 0011_ms2` (solicitud de
cancelación) y `0010_outbox_eventos_ms2 → 0011_disponibilidad_repuestos_ms2`
(idempotencia), cada una con su propio head. Se resolvió con la migración de merge
`0012_unir_cancelacion_eventos_ms2.py`
(`down_revision = ("0011_ms2", "0011_disponibilidad_repuestos_ms2")`). En MS1 pasó lo
mismo con `0005_unir_login_notificaciones_ms1.py`.

**Diagnóstico y arreglo:**
```powershell
python -m alembic -c services/ms2_taller/alembic.ini heads      # más de una línea = problema
python -m alembic -c services/ms2_taller/alembic.ini merge -m "unir X e Y" <head1> <head2>
```
`scripts/inicializar_bd.py` usa `upgrade heads` (en plural) para no fallar, pero la
solución es el merge: con dos heads, el orden entre ramas no está garantizado.

### Drift (el modelo ORM y las migraciones no describen lo mismo)

**Síntoma:** `alembic check` falla, o `revision --autogenerate` propone cambios que nadie
pidió (por ejemplo, borrar índices).

**Ejemplo real (MIG-2):** los índices GIN `ix_*_trgm` de MS3 existen en
`0006_indices_busqueda_ms3.py` pero no en el modelo. `compare_metadata` devuelve
`remove_index ix_repuesto_nombre_trgm`. Hoy se acepta a propósito en
`DIFERENCIAS_ACEPTADAS` de `tests/test_integridad_referencial_servicios.py`.

**Cómo verlo:**
```python
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
with engine.connect() as c:
    print(compare_metadata(MigrationContext.configure(
        c, opts={"compare_type": True, "compare_server_default": True}), Base.metadata))
```
Una lista vacía significa que no hay drift. Sin `compare_type`, un `String(120)` contra
un `String(200)` pasa inadvertido.

### Downgrade roto y convención de nombres

**Ejemplo real (MIG-1):** `downgrade base` de MS2 falla con
`constraint "ck_cliente_ck_cliente_usuario_id_positivo" does not exist`. La
`NAMING_CONVENTION` de `shared/db.py` antepone `ck_<tabla>_` a los nombres.
`0002_restricciones_ms2.py` crea el CHECK con `"usuario_id_positivo"` (bien), pero lo
borra con `"ck_cliente_usuario_id_positivo"`, que queda con doble prefijo.
**Regla:** en `drop_constraint` usar el mismo nombre corto que en `create_*`, o
marcar el nombre final con `op.f("ck_cliente_usuario_id_positivo")` para que no se
vuelva a convertir.

### Lock (la migración "se cuelga")

**Síntoma:** `upgrade` no avanza. Un `ALTER TABLE` necesita un bloqueo
`ACCESS EXCLUSIVE` y espera a cualquier transacción que esté usando la tabla (también
una que quedó *idle in transaction*).

**Diagnóstico** (en otra conexión):
```sql
SELECT pid, state, wait_event_type, now() - xact_start AS duracion, left(query, 60)
FROM pg_stat_activity WHERE datname = current_database() AND state <> 'idle';
SELECT pid, pg_blocking_pids(pid) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0;
```
**En el repo:**
- Dos procesos no migran la misma base a la vez: `inicializar_bd.py` toma
  `pg_try_advisory_lock(0x5347544D)` y, si no lo obtiene en 120 s, informa
  *"otro proceso está migrando esta base (candado ocupado)"*.
- Para no quedarse esperando sin límite se pone un tope, como en `datos_demo.py`
  (`SET LOCAL lock_timeout = '10s'`) y en `verificar_migraciones.py`
  (`SET LOCAL statement_timeout = '5s'`).

## 2. Sesión (SQLAlchemy)

La configuración común está en `shared/db.py`: `autoflush=False`,
`expire_on_commit=False` y `get_db()` hace rollback y `close()` siempre.

### Objetos expirados / `DetachedInstanceError`

- Con `expire_on_commit=True` (valor por omisión de SQLAlchemy), después del `commit()`
  todo atributo se vuelve a leer de la base. Si la sesión ya se cerró, aparece
  `DetachedInstanceError`. En el repo se usa `False`: así MS3 puede cerrar la
  transacción de lectura antes de llamar a MS2 (`UnidadDeTrabajo.liberar_conexion`) y
  seguir usando los objetos.
- `refresh(obj, attribute_names=[...])` relee solo lo que escribe la base. Ejemplo:
  `decidir_version` relee `bloqueada_en`, que completa un trigger.

### Lazy load fuera de la sesión (y N+1)

**Síntoma:** `DetachedInstanceError: Parent instance ... is not bound to a Session;
lazy load operation of attribute 'proveedor' cannot proceed`, o cientos de `SELECT`
iguales en el log.
**Diagnóstico:** activar `MS3_DB_ECHO=true` o contar sentencias con
`event.listen(conexion, "before_cursor_execute", ...)`, como hace
`services/ms3_presupuestos/tests/test_consultas_decision.py`.
**En el repo:** `Repuesto.proveedor` usa `lazy="selectin"`: un lote de repuestos trae
sus proveedores en una sola consulta. Para prohibir un lazy load en un camino crítico se
puede usar `raiseload()`.

### Flush: cuándo se envía el SQL

- `flush()` envía los INSERT/UPDATE sin confirmar. Los repositorios de MS3 hacen
  `add()` + `flush()` en `agregar()` para que la base valide en ese momento y el error
  salga en la línea que lo causó, no en el commit.
- **Caso real (SES-1):** `SAWarning: Object of type <MovimientoInventario> not in
  session, add operation along 'Repuesto.movimientos' will not proceed`. Se construyó
  `MovimientoInventario(repuesto=repuesto)` y luego `begin_nested()` hizo autoflush antes
  del `add()`. El backref ya había metido el objeto en la colección, pero en SQLAlchemy
  2.0 eso no lo agrega a la sesión. Solo pasaba en las pruebas, porque su sesión tiene
  `autoflush=True` y la de producción no. Ahora las pruebas de MS3 convierten toda
  `SAWarning` en error (`services/ms3_presupuestos/tests/conftest.py`).
- **Lecturas repetidas (SES-2):** `populate_existing=True` en un `FOR UPDATE` relee la
  fila y sus relaciones selectin. Si se bloquea dos veces en la misma transacción, todo
  se lee dos veces. La solución fue bloquear una vez y pasar el resultado
  (`disponibilidad.bloquear_y_leer_compromisos`).

## 3. Transacciones (PostgreSQL)

### Rollback

- **`InFailedSqlTransaction` / *"current transaction is aborted"*:** después de un
  error, PostgreSQL rechaza todo hasta un `ROLLBACK`. En SQLAlchemy:
  *"This Session's transaction has been rolled back due to a previous exception during
  flush"*. Hay que hacer `rollback()`, o aislar el intento en un SAVEPOINT.
- **En el repo:** `UnidadDeTrabajo.transaccion()` (MS3) hace commit al final o rollback
  ante cualquier excepción. Si se anida, abre `begin_nested()` (SAVEPOINT): un error
  interno revierte solo ese bloque. `_manejar_errores` traduce `IntegrityError` a
  `ConflictoDeDatos` / `ReglaDeDatosViolada`.
- **Prueba de que es atómico:**
  `test_si_falla_despues_de_registrar_la_decision_no_queda_nada`
  (`test_operaciones_presupuesto.py`) fuerza un error después del INSERT y verifica que
  no quedó la decisión ni el bloqueo del trigger.

### Aislamiento y concurrencia

- PostgreSQL usa por omisión `READ COMMITTED`: dos transacciones pueden leer el mismo
  stock y las dos "reservarlo". El repo lo evita con bloqueos de fila, no subiendo el
  nivel de aislamiento:
  - `RepositorioRepuestos.bloquear_varios` hace `FOR UPDATE` **siempre en orden de id**,
    para que dos aprobaciones simultáneas esperen en vez de producir un *deadlock*.
  - Las colas usan `with_for_update(skip_locked=True)`
    (`ms2_taller/services/publicador_eventos.py`, `ms1_auth/services/entregas_notificaciones.py`):
    cada worker toma filas distintas.
- **Diagnóstico de deadlock:** `deadlock detected` en el log de PostgreSQL, con las dos
  sentencias. Buscar dos caminos que bloquean las mismas tablas en distinto orden.

### Advisory locks

- Son candados con nombre (un número) que no bloquean filas. Sirven para "solo un
  proceso hace X". `inicializar_bd.py` usa `pg_try_advisory_lock` (no espera, reintenta
  cada 1 s) y libera en un `finally` con `pg_advisory_unlock`.
- Los de sesión duran mientras la conexión esté abierta: si el proceso muere, se
  liberan solos. Si la conexión vuelve al pool sin `unlock`, el candado queda tomado.
  Por eso `_tomar_candado` usa una conexión propia y la cierra en el `finally`.
- **Ver quién lo tiene:**
  ```sql
  SELECT l.pid, a.application_name, a.state FROM pg_locks l
  JOIN pg_stat_activity a USING (pid) WHERE l.locktype = 'advisory';
  ```

## Checklist rápido

| Síntoma | Primer comando | Tipo |
|---|---|---|
| `Multiple head revisions` | `alembic -c ... heads` | Migración |
| `autogenerate` propone borrar cosas | `python scripts/diagnosticar_migraciones.py <servicio>` | Migración (drift) |
| `downgrade` falla con "does not exist" | revisar los nombres contra `NAMING_CONVENTION` | Migración |
| La migración no avanza | `pg_stat_activity` + `pg_blocking_pids` | Transacción (lock) |
| `DetachedInstanceError` | ¿la sesión se cerró? ¿`expire_on_commit`? | Sesión |
| `SAWarning ... not in session` | ¿el objeto se armó con una relación antes del `add`? | Sesión |
| Muchos `SELECT` iguales | contar sentencias (`before_cursor_execute`) | Sesión / modelo ORM |
| `current transaction is aborted` | falta un `rollback()` o un SAVEPOINT | Transacción |
| `deadlock detected` | ver el orden de los `FOR UPDATE` | Transacción |
| "candado ocupado" | `pg_locks` con `locktype = 'advisory'` | Transacción |
