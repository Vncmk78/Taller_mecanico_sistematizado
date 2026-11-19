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

## Pendientes

- Quedan 13 lecturas repetidas: `reservas.ajustar_reserva` vuelve a bloquear los
  repuestos y a leer lo comprometido que `disponibilidad.evaluar` ya leyó. Unificarlo
  cambia la forma de calcular faltantes; conviene acordarlo antes.
- Hallazgo para la tarea bloqueada de Bastián: los índices GIN de búsqueda de MS3
  (`ix_*_trgm`, `0006_ms3`) existen en la migración pero no en el modelo, por lo que
  `alembic revision --autogenerate` propondría borrarlos.
