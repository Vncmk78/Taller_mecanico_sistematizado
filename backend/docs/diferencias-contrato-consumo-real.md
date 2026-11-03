# Diferencias entre el contrato publicado y el consumo real

**Semana 8 — Registrar diferencias entre contratos publicados y consumo real.**

Registro de lo que el contrato OpenAPI 1.0.0 de la Gateway
(`docs/openapi/sgtm-gateway-1.0.0.json`) dice y lo que **de verdad** pasa al
consumirlo. Este documento **registra** las diferencias. Corregirlas le toca a
la tarea «Corregir normalización de respuestas y errores detectados» y al equipo
dueño de cada parte.

- Consumo declarado del frontend: `gateway/contratos/consumo_web.py`
- Verificación automática: `tests/test_contrato_consumo_real.py`
- Contrato: [`versionado-contrato-openapi.md`](versionado-contrato-openapi.md)

---

## 1. Qué se comparó

| Fuente de consumo real | Cómo se obtuvo | Contra qué se compara |
|---|---|---|
| **Frontend web** | Lectura de `frontend/src/infrastructure/api/*Service.ts`: las 23 llamadas HTTP, los campos que cada interfaz `*Api` lee y los cuerpos que arma cada servicio. Quedó declarado en `consumo_web.py` | Esquemas del contrato 1.0.0: la operación y el estado existen, los campos están publicados, el tipo, la obligatoriedad, el `null`, los enums y el body aceptado |
| **Respuestas reales de la Gateway** | Gateway real + MS1 y MS2 reales in-process (fixture `ecosistema`, SQLite en memoria). Se recorren los flujos de Cliente, Mecánico y Administrador: 26 llamadas con éxitos y errores (401, 403, 404, 422, 200/201) | Cada body se valida con `jsonschema` contra el esquema publicado para **ese** estado, y se buscan campos reales que el contrato no publica |
| **App móvil (Integra IV)** | Todavía no hay código en el repositorio, así que no hay consumo real que medir | Su catálogo de 25 operaciones ya está validado en `contratos-integracion-iv.md` |

## 2. Resultado

| | Revisado | Coincide | Diferencias |
|---|---:|---:|---:|
| Llamadas del frontend web | 23 | 18 | 5 llamadas, 2 diferencias (D-01, D-02) |
| Respuestas reales de la Gateway | 26 respuestas (17 operaciones) | 26 | 0 |
| Diferencias de semántica (no detectables por esquema) | — | — | 1 (D-03) |

**Las respuestas reales cumplen el contrato publicado**: los 26 bodies, de
éxito y de error, validan contra el esquema de su estado y no traen campos sin
publicar. Las diferencias están del lado de **cómo el frontend lee** el
contrato.

## 3. Registro de diferencias

| ID | Severidad | Dónde | Qué dice el contrato | Qué pasa en el consumo real | Efecto | Dueño sugerido |
|---|---|---|---|---|---|---|
| **D-01** | **Alta** | `OrderService.cancelarComoCliente` → `POST /api/ordenes/{orden_id}/cancelacion` | Responde `201`/`200` con `SolicitudCancelacionRespuesta` (`solicitud_id`, `estado: "pendiente"`, …). **La orden no cambia de estado** hasta que un Administrador confirma | El frontend tipa la respuesta como `OrdenRespuesta` y la pasa por `mapOrdenApi`: lee `estado_codigo`, `vehiculo_id`, `ingreso_id`, `mecanico_actual_id`, `creado_por_id`, `creado_en` y `actualizado_en`, que **no vienen** | `OrderActionsPanel` llama a `updateOrder()` con una orden con campos `undefined` (corrompe el estado local) y muestra «actualizada a …» con una etiqueta vacía. El test del panel no lo detecta porque simula la respuesta como una orden en estado 8 | Frontend |
| **D-02** | Baja | `token_type` (login), `repuestos` (bitácora GET/POST), `decision_id` y `aplicacion_en_orden` (decisión de presupuesto) | Campos publicados como **opcionales**: tienen valor por defecto en el modelo y el esquema se genera en modo validación | Las respuestas reales **siempre** los traen (verificado en vivo para login y bitácora). El frontend los lee como siempre presentes | Sin falla hoy. Un cliente generado desde el OpenAPI (por ejemplo la app móvil) los tiparía como opcionales y tendría que tratar un `undefined` que nunca llega | Backend (Gateway): marcarlos obligatorios en 1.0.1 (PATCH) |
| **D-03** | Media | `AuthService.toDomainUser` (`/api/auth/login`, `/api/auth/me`) | `roles` es una lista; los roles **se acumulan** (unión de alcances, `matriz-autorizacion-roles.md` §3.1). El contrato no garantiza ningún orden | El frontend toma solo `roles[0]` como rol de la sesión. MS1 ordena alfabéticamente, así que un usuario `cliente` + `mecanico` entra siempre como Cliente y uno `administrador` + `mecanico` siempre como Administrador | Un usuario multirol no puede usar su segundo portal. Depende de un orden que el contrato no publica | Frontend (elegir portal), o contrato (publicar el orden) |

Las diferencias que detecta el esquema (D-01 y D-02) están marcadas en
`tests/test_contrato_consumo_real.py` como `xfail` estricto con su ID:

| Llamada | ID |
|---|---|
| `OrderService.cancelarComoCliente` | D-01 |
| `AuthService.login` | D-02 |
| `OrderService.getOrderBitacora` | D-02 |
| `OrderService.registrarBitacora` | D-02 |
| `PresupuestoService.decidir` | D-02 |

Además, `test_d01_la_cancelacion_real_no_trae_los_campos_de_orden` deja la
evidencia viva de D-01: la respuesta real trae `solicitud_id` y
`estado: "pendiente"`, y no trae `estado_codigo` ni `vehiculo_id`.

## 4. Observaciones (no son diferencias del contrato)

- **O-01 — Fechas sin zona horaria en el entorno de prueba.** Con SQLite, MS2
  devuelve `creado_en` como `2026-11-03T15:53:47`, sin desfase. Los ejemplos
  publicados usan `-03:00` y PostgreSQL (`timestamptz`) sí lo incluye. Hay que
  confirmarlo con PostgreSQL antes de exigir `format: date-time` estricto.
- **O-02 — El 429 de login no se trata aparte en el frontend.** El contrato lo
  publica desde 1.0.0 con `Retry-After`. `errors.ts` muestra el `detail`
  («Demasiados intentos fallidos…»), pero no usa la espera.
- **O-03 — Cancelación repetida.** El contrato distingue `201` (creada) de `200`
  (ya existía). El frontend no los distingue; no es un problema mientras D-01
  siga abierta, pero conviene considerarlo al corregirla.

## 5. Qué no se verificó en vivo

| Llamadas | Motivo | Cobertura existente |
|---|---|---|
| `PresupuestoService.*` (MS3) | Necesitan datos en MS3 y la coordinación MS3 → MS2 por HTTP, que el fixture `ecosistema` no conecta | Comparación estática de esta tarea (sin diferencias salvo D-02) y `test_ms3_presupuestos_contratos.py` |
| `EvidenciaService.*` (MS4) | Necesitan almacenamiento S3 simulado y un verificador de órdenes | Comparación estática de esta tarea (sin diferencias) y `test_gateway_openapi_evidencias.py` (ejemplos contra respuestas reales de MS4) |
| `AuthService.listarUsuarios` | Pantalla de administración | Comparación estática (sin diferencias) |

## 6. Cómo ejecutar

```bash
cd backend
python -m pytest tests/test_contrato_consumo_real.py -v
```

Resultado esperado hoy: `22 passed, 5 xfailed`.

Si el frontend cambia lo que lee o envía, se actualiza
`gateway/contratos/consumo_web.py` en el mismo cambio. Si una diferencia se
corrige, su prueba pasa a XPASS: hay que quitarla de `_DIFERENCIAS_WEB` y
marcarla «Corregida» en este documento.
