# Cierre de presupuestos e inventario: A-03, A-04 y verificación con PostgreSQL real

Responsable: Martín López · Fecha: 2026-11-09 · Rama `MartinL`.
Referencia: «Auditoría y plan exigible SGTM» (5 nov 2026), hallazgos A-03 y A-04
y recorrido de inventario y proveedores.

## Ambiente y versión probada

| Elemento | Valor |
|---|---|
| Código base | `main` en `4012fe5` (incluye `87cb4e5` de Martín H: primera versión de la revisión administrativa y del reintento) |
| Ambiente | `sgtm_pruebas` (`scripts/ambiente_pruebas.py`): Gateway 8100, MS1–MS4 8101–8104, web 5183 |
| Bases | PostgreSQL 16.15, cuatro bases `taller_msN_pruebas`, más bases privadas `verificar_suite_*` para la suite |
| Objetos | MinIO (bucket `evidencias-pruebas`) |
| Contrato | Gateway 3.0.0 (`docs/openapi/sgtm-gateway-3.0.0.json`) |
| Herramientas | Python 3.13.18, Node 22.23.4, Chromium 153 (Playwright) |
| Datos | `datos_demo.py reiniciar` antes de los recorridos (cuentas `*@pruebas.cl`, catálogo base, DEMO01–09) |
| Fallos controlados | `scripts/proxy_fallos_ms2.py` entre MS3 y MS2 (`MS3_MS2_URL=http://127.0.0.1:8112`) |

## Punto 1 — Revisión y envío del presupuesto (A-03)

**Commit:** `b289eba` (usa el dominio de `7909d89`).

**Archivos:** `frontend/src/presentation/components/budgets/BudgetEditor.tsx`,
`frontend/src/presentation/pages/mechanic/MechanicBudgetPage.test.tsx`,
`backend/scripts/e2e_web_presupuestos.py`,
`backend/scripts/e2e_presupuestos_revision_recuperacion.py` (R1).

**Qué se hizo** (sobre la base de Martín H en `87cb4e5`, que ya separaba la ruta
del Mecánico de `/admin/ordenes/:id/presupuesto`):

- Mecánico: prepara y guarda el borrador; no recibe «Enviar al cliente». La
  pantalla le explica que un Administrador revisa los precios y lo envía.
- Cuenta Mecánico+Administrador: ve además el enlace «Revisar y enviar como
  Administrador», según sus roles reales (`roles` de la cuenta, no solo el portal).
- Administrador: desde el detalle de la orden («Revisar presupuesto y precios»)
  corrige precios y envía. El aviso solo dice que la orden avanzó si la API lo
  confirmó (`aplicacion_en_orden`).
- Backend sin cambios: el envío sigue protegido por `_solo_administrador`.
- Corrección encontrada en la prueba web: una lectura tardía del presupuesto
  pisaba lo que el Administrador ya había escrito y se enviaba el precio
  anterior. Ahora el formulario no se reemplaza si la persona ya lo editó.

**Pruebas y resultado**

| Prueba | Resultado |
|---|---|
| API real, R1 (`e2e_presupuestos_revision_recuperacion.py`) | Mecánico → **403**; Cliente+Mecánico → **403**; Administrador corrige 20.000 → 32.500 y envía → 200, orden en 3; Cliente ve v1 enviada con 32.500; Mecánico+Administrador → 200 |
| Web real (`e2e_web_presupuestos.py`, comprobaciones A-03) | 4/4 |
| Vitest `MechanicBudgetPage.test.tsx` | 9/9 (solo Mecánico, multirrol, envío administrativo) |

**Evidencia:** `evidencia/2026-11-09-presupuestos-inventario/capturas/a03-1-mecanico-borrador.png`,
`a03-2-administrador-envia.png`, `a03-3-cliente-consulta.png`; informe
`e2e-api-presupuestos.md` (flujo R1).

## Punto 2 — Recuperación de presupuestos que responden 503 (A-04)

**Commit:** `7909d89` (y la parte del Administrador en `b289eba`).

**Archivos:** `frontend/src/domain/entities/Presupuesto.ts` (`aplicacionPendiente`),
`frontend/src/domain/entities/aplicacionPendiente.test.ts`,
`frontend/src/presentation/hooks/useEstadoOrden.ts`,
`frontend/src/presentation/components/budgets/PresupuestoAplicacionPanel.tsx` y su prueba,
`frontend/src/presentation/pages/client/ClientBudgetDetailPage.tsx` y su prueba,
`backend/scripts/proxy_fallos_ms2.py`, `backend/scripts/e2e_presupuestos_revision_recuperacion.py`.

**Qué se hizo**

- Se distinguen tres casos: 503 **sin referencia** (falló antes de guardar: error
  normal); 503 **con `presupuesto_id` o `decision_id`** (guardado, falta aplicar);
  y respuesta perdida (resultado incierto, ya existía).
- El caso pendiente muestra «Envío/Decisión registrada, pendiente de aplicar»,
  la referencia (n°) y solo el botón «Reintentar aplicación en la orden», que usa
  `/envio-inicial/aplicacion` o `/decisiones/{id}/aplicacion`. «Enviar» y
  «Aprobar/Rechazar» quedan ocultos o bloqueados.
- La referencia no depende de la pestaña: al volver a la página, la web lo
  **deduce del servidor** (versión ya enviada con la orden en 1–2, o decisión
  inicial con la orden aún en 3). Antes, el panel aparecía siempre que había una
  versión enviada, aunque ya estuviera aplicada.
- Tras un reintento exitoso se vuelven a leer presupuesto y orden y recién ahí se
  confirma el resultado. Si el reintento falla, se muestra el motivo y se puede
  volver a intentar.

**Pruebas y resultado**

| Prueba | Resultado |
|---|---|
| API real con fallo controlado (R2–R4) | 56/56 pasos HTTP y 19/19 comprobaciones de datos, todo el informe |
| R2: verificación de la orden caída | 503 sin referencia; versión sigue en borrador; 0 envíos en BD |
| R3: coordinación del envío caída | 503 con `presupuesto_id` y ruta; reintento con MS2 caído → 503; Mecánico no puede reintentar (403); recuperación → 200; reintento repetido → 200; reenviar → 409; **1** transición a 3 (API y `historial_estado`); **1** envío en MS3 |
| R4: coordinación de la decisión caída | 503 con `decision_id`; versión aprobada; reintento caído → 503; Administrador no puede aplicar la decisión del cliente (403); recuperación → 200; orden en 5; decidir otra vez → 409; **1** transición desde 3; **1** decisión en MS3 |
| Web real (`e2e_web_presupuestos.py`, comprobaciones A-04) | 10/10, con recarga de página en medio y reintento fallido antes de recuperar |
| Vitest panel, dominio, cliente, editor | 3 + 7 + 13 + 9 = 32, todo aprobado |

**Evidencia:** capturas `a04-1-envio-pendiente.png` … `a04-5-decision-recuperada.png`;
informe `e2e-api-presupuestos.md` con las llamadas bloqueadas por el proxy.

**Hallazgo (no corregido, contrato compartido):** el contrato 3.0.0 solo publica
para el envío el 503 «guardado, pendiente». El 503 previo al guardado
(`{"detail": "No fue posible validar la orden..."}`) existe pero no está
publicado. Lo debe decidir quien mantiene el contrato (Martín H).

## Punto 3 — Presupuestos e inventario con PostgreSQL real

**Commit:** `f64a033`.
**Archivos:** `backend/services/ms3_presupuestos/tests/test_cierre_presupuestos_inventario.py` (nuevo).

**Comandos**

```bash
cd backend
python scripts/ambiente_pruebas.py configurar && python scripts/ambiente_pruebas.py infra
# Suites de MS3 y de integración presupuesto/stock, con bases privadas verificar_suite_*
python scripts/verificar_backend.py services/ms3_presupuestos/tests \
  tests/test_decisiones_presupuesto_postgresql.py tests/test_integracion_presupuesto_stock.py \
  tests/test_disponibilidad_repuestos.py tests/test_ms3_persistencia_base.py \
  tests/test_ms3_presupuestos_contratos.py tests/test_decisiones_presupuesto_integracion.py \
  tests/test_ms3_aislamiento.py tests/test_ms3_estructura.py tests/test_ms3_integracion_ms2.py \
  tests/test_ms2_integracion_ms3.py
# Suite completa del backend
python scripts/verificar_backend.py
```

**Resultado**

- Suites de MS3 y de integración: **687 aprobadas, 0 omitidas, 0 fallidas**
  (JUnit: `tests=687 skipped=0 failures=0 errors=0`).
- Suite completa del backend con PostgreSQL y MinIO reales: **2789 aprobadas,
  0 omitidas**.
- Casos nuevos (3/3 aprobados, con hilos reales sobre un esquema migrado).

| Exigencia | Pruebas que la cubren (todas ejecutadas sin omisiones) |
|---|---|
| Versión enviada o aprobada no se sobrescribe | `test_version_enviada_no_se_edita_409`, `test_version_aprobada_no_se_edita_409`, `test_la_base_impide_tocar_la_version_aprobada`, `test_sql_directo_tampoco_rompe_la_version_aprobada`, `test_editar_y_enviar_a_la_vez_nunca_cambia_una_version_enviada` |
| Rechazar una modificación conserva la aprobación | `test_rechazar_modificacion_conserva_la_aprobacion_vigente`, `test_rechazar_modificacion_mantiene_vigente_la_ultima_aprobada`, `test_modificacion_sin_stock_conserva_la_reserva_anterior` |
| Disponibilidad considera reservas de otras órdenes | `test_consumo_no_toma_unidades_reservadas_por_otra_orden`, `test_no_alcanza_si_hay_que_tomar_lo_reservado_por_otra_orden`, `test_otra_orden_que_reservo_antes_deja_a_esta_esperando` |
| Operaciones simultáneas sin stock negativo ni reservas indebidas | `test_dos_consumos_simultaneos_nunca_dejan_stock_negativo`, `test_compromisos_simultaneos_no_sobrevenden`, `test_dos_decisiones_simultaneas_solo_registra_una` y **nuevo** `test_aprobaciones_simultaneas_no_reservan_unidades_de_otra_orden` (stock 3, dos órdenes piden 2: una reserva 2, la otra 0, stock físico intacto) |
| Repetir consumos o movimientos no duplica | `test_la_misma_clave_en_paralelo_se_aplica_una_vez`, `test_misma_clave_no_descuenta_dos_veces`, `test_reintentar_la_aplicacion_no_reserva_dos_veces` |
| Un fallo revierte la transacción | `test_error_en_el_caso_de_uso_revierte_todo`, `test_error_de_outbox_revierte_stock_y_movimiento`, `test_error_al_encolar_revierte_envio_del_presupuesto`, `test_movimiento_rechazado_no_deja_rastro` |
| Movimientos con orden, repuesto, cantidad, responsable y fecha | `test_cada_movimiento_queda_con_su_clave_fija_y_quien_lo_registro`, `test_el_movimiento_trae_su_fecha_en_el_mismo_insert` y **nuevo** `test_consumo_conserva_orden_repuesto_cantidad_responsable_y_fecha` |
| Alertas: particular o general y stock < umbral estricto | `test_bajo_umbral_usa_el_particular_o_el_general`, `test_igualdad_no_alerta_particular_prevalece_y_movimiento_repetido_no_duplica` y **nuevo** `test_alerta_con_umbral_general_es_estricta` |

**Evidencia:** este documento, `.pruebas/logs/suite-backend.{log,xml}` de cada
ejecución (no se versionan) y el resumen JUnit anterior.

## Punto 4 — Recorrido web de inventario y proveedores

**Commit:** `e6c6b9a`.
**Archivos:** `frontend/src/presentation/pages/admin/AdminInventoryMovementsPage.tsx`,
`AdminInventoryMovementsPage.trazabilidad.test.tsx` (nuevo), `backend/scripts/e2e_web_inventario.py`.

**Qué se ajustó sobre main:** la tabla de movimientos muestra el nombre del
repuesto y la columna **Responsable**. Con stock insuficiente, el formulario
detalla lo que falta («faltan 3 (disponible 2, solicitado 5). No se registró
ningún cambio.») en vez de solo el texto del servidor.

**Recorrido verificado (11/11), comparando cada pantalla con la API y la BD:**
crear proveedor oficial → crear repuesto (stock 4, umbral 3) → detalle de stock
igual a la API → ajuste −2 (aparece en Alertas) → ajuste −5 rechazado sin cambios
→ ingreso +1 (stock 3 = umbral: sale de Alertas) → umbral general cambiado con
observación y restaurado (historial) → movimientos con responsable → el Cliente
ve «Origen: <proveedor>» en su presupuesto.

**Evidencia:** capturas `inv-1-proveedor.png` … `inv-8-procedencia-cliente.png`, `web-inventario.txt`.

**Cómo lo repite otra persona** (los nombres llevan un sufijo aleatorio: se puede repetir):

```bash
cd backend
python scripts/ambiente_pruebas.py configurar && python scripts/ambiente_pruebas.py infra
python scripts/ambiente_pruebas.py migrar && python scripts/ambiente_pruebas.py iniciar
SGTM_ENV_FILE=.env.pruebas python scripts/datos_demo.py reiniciar --confirmar LIMPIAR-DEMO \
  --gateway http://127.0.0.1:8100 --perfil local
# Fallos controlados (solo para A-04): MS3 detrás del proxy
kill $(cat .pruebas/ms3.pid)
python scripts/proxy_fallos_ms2.py --puerto 8112 --destino http://127.0.0.1:8102 &
python scripts/ambiente_pruebas.py ejecutar -- env MS3_MS2_URL=http://127.0.0.1:8112 \
  python -m uvicorn services.ms3_presupuestos.main:app --host 127.0.0.1 --port 8103 &
# Recorridos
python scripts/ambiente_pruebas.py ejecutar -- python scripts/e2e_presupuestos_revision_recuperacion.py --salida informe.md
python scripts/ambiente_pruebas.py ejecutar -- python scripts/e2e_web_presupuestos.py --capturas capturas
python scripts/ambiente_pruebas.py ejecutar -- python scripts/e2e_web_inventario.py --capturas capturas
```

Requiere `pip install playwright && python -m playwright install chromium`.
Cada recorrido crea órdenes asignadas al Mecánico de prueba (máximo 20 activas):
si se repite muchas veces, ejecutar antes `datos_demo.py reiniciar`.

## Pruebas del frontend

`npm run lint` sin errores (solo los 2 avisos previos de notificaciones),
`tsc -b` sin errores, `npm test`: **127 archivos, 1092 pruebas aprobadas**.

## Pendientes

1. **Contrato 3.0.0:** publicar el 503 de envío previo al guardado o unificar su
   cuerpo. Decisión de Martín H.
2. **Coordinación con Martín H:** se modificaron archivos de su commit `87cb4e5`
   (`BudgetEditor.tsx`, `PresupuestoAplicacionPanel.tsx`, `ClientBudgetDetailPage.tsx`
   y sus pruebas). Deben revisarlos antes de integrar en `Develop`.
3. **Ambiente integrado (Kubero/Vercel):** los recorridos se ejecutaron en el
   ambiente local de pruebas con servicios reales. Falta repetir R1–R4 y los
   recorridos web en el despliegue compartido.
4. El formulario de movimientos pide el **ID** del repuesto; un selector por
   nombre sería más claro (mejora de UX, no bloquea).
5. Las reservas creadas al aprobar quedan con el Cliente como responsable
   (`Usuario #1`), porque la aprobación las genera. Confirmar con el equipo si
   así debe mostrarse.
