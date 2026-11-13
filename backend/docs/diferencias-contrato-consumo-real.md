# Diferencias entre el contrato publicado y el consumo real

**Semana 8 — Registrar diferencias entre contratos publicados y consumo real.**
**Actualizado:** Semana 8 — Corregir normalización de respuestas y errores detectados.

Registro de lo que el contrato OpenAPI de la Gateway
(`docs/openapi/sgtm-gateway-<versión>.json`; medido sobre 1.0.0 y revisado en 2.0.1) dice y lo que **de verdad** pasa al
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
| **Frontend web** | Lectura de `frontend/src/infrastructure/api/*Service.ts`: las llamadas HTTP (23 al registrar, 25 tras la corrección), los campos que cada interfaz `*Api` lee y los cuerpos que arma cada servicio. Quedó declarado en `consumo_web.py` | Esquemas del contrato 1.0.0: la operación y el estado existen, los campos están publicados, el tipo, la obligatoriedad, el `null`, los enums y el body aceptado |
| **Respuestas reales de la Gateway** | Gateway real + MS1 y MS2 reales in-process (fixture `ecosistema`, SQLite en memoria). Se recorren los flujos de Cliente, Mecánico y Administrador: 29 llamadas con éxitos y errores (401, 403, 404, 422, 200/201) | Cada body se valida con `jsonschema` contra el esquema publicado para **ese** estado, y se buscan campos reales que el contrato no publica |
| **App móvil (Integra IV)** | Todavía no hay código en el repositorio, así que no hay consumo real que medir | Su catálogo de 25 operaciones ya está validado en `contratos-integracion-iv.md` |

## 2. Resultado

| | Al registrar (1.0.0) | Tras la corrección (2.0.1) |
|---|---:|---:|
| Llamadas del frontend web que coinciden con el contrato | 18 de 23 | **25 de 25** |
| Respuestas reales que cumplen el esquema publicado | 26 de 26 (17 operaciones) | **29 de 29 (19 operaciones)** |
| Diferencias abiertas | 3 (D-01, D-02, D-03) | **0** (D-04, registrada el 7/11/2026, corregida en 2.2.1) |

Las respuestas reales siempre cumplieron el contrato publicado: las
diferencias estaban en cómo el frontend lo leía (D-01, D-03) y en un contrato
menos preciso que la respuesta real (D-02).

## 3. Registro de diferencias

| ID | Severidad | Dónde | Qué decía el contrato | Qué pasaba en el consumo real | Estado |
|---|---|---|---|---|---|
| **D-01** | Alta | `OrderService.cancelarComoCliente` → `POST /api/ordenes/{orden_id}/cancelacion` | Responde `SolicitudCancelacionRespuesta` (`solicitud_id`, `estado: "pendiente"`); la orden no cambia de estado hasta que un Administrador confirma | El frontend leía la respuesta como `OrdenRespuesta`: `estado_codigo`, `vehiculo_id` y los demás campos de orden llegaban `undefined` y se guardaban en el estado local | **Corregida** en el frontend (SCRUM-706, Martín): ya no lee la respuesta y vuelve a pedir la orden con `getOrderById`. `consumo_web.py` ya lo refleja |
| **D-02** | Baja | `token_type` (login), `repuestos` (bitácora), `decision_id` y `aplicacion_en_orden` (decisión de presupuesto) | Publicados como opcionales (tienen valor por defecto) | Siempre vienen en la respuesta (verificado en vivo) | **Corregida** en el contrato **2.0.1**: los modelos de respuesta marcan obligatorios sus campos con valor por defecto, en la Gateway y en MS1, MS2 y MS3. Ver `versionado-contrato-openapi.md` |
| **D-03** | Media | `AuthService.toDomainUser` (`/api/auth/login`, `/api/auth/me`) | `roles` es una lista y los roles se acumulan (`matriz-autorizacion-roles.md` §3.1) | El frontend guardaba solo `roles[0]`: las guardas de ruta (`getUserRoles`, `hasAnyRole`), que ya soportaban varios roles, nunca los recibían, y un usuario `cliente` + `mecanico` (ingresa como Cliente) no podía entrar a las rutas de mecánico | **Corregida** en el frontend: `User.roles` conserva todos los roles válidos y las guardas los usan. El **portal de ingreso** sigue siendo el primero de la lista (MS1 los ordena alfabéticamente); cambiar esa preferencia es una decisión de producto, no de contrato |

| **D-04** | Baja | `ConfiguracionTallerService` (`GET` y `PUT /api/ordenes/configuracion/capacidad/mecanicos`, página Capacidad del taller) | `mecanicos_sobre_limite` es `list[dict[str, int]]`: no nombra las claves de cada elemento | MS2 siempre devuelve `{"mecanico_id", "ordenes_activas"}` (`services/capacidad_mecanicos.py`) y la web lee ambas para avisar qué mecánicos superan el límite | **Corregida** en el contrato **2.2.1**: el elemento se tipa como `MecanicoSobreLimite` (`mecanico_id`, `ordenes_activas`) en MS2 y en la Gateway; el JSON no cambia |

`_DIFERENCIAS_WEB` en `tests/test_contrato_consumo_real.py` vuelve a quedar
vacío. Una diferencia nueva se registra ahí como `xfail` estricto con un ID
nuevo (D-05, …).

`test_d01_la_cancelacion_real_no_trae_los_campos_de_orden` se conserva como
evidencia viva de que la cancelación responde una solicitud, no una orden.

**Regresión (Semana 9):** cada incompatibilidad corregida (B-01 a B-04, D-01,
D-02, H-01 y O-01) tiene una prueba con su ID en
`tests/test_regresion_incompatibilidades.py` y
`tests/test_cabeceras_cliente_movil.py`. Al corregir una nueva, se agrega ahí
con su ID.

## 4. Observaciones (no son diferencias del contrato)

- **O-01 — Fechas sin zona horaria en el entorno de prueba.** Con SQLite, MS2
  devuelve `creado_en` como `2026-11-03T15:53:47`, sin desfase. Los ejemplos
  publicados usan `-03:00` y PostgreSQL (`timestamptz`) sí lo incluye. Hay que
  confirmarlo con PostgreSQL antes de exigir `format: date-time` estricto.
- **O-02 — El 429 de login no se trata aparte en el frontend.** El contrato lo
  publica desde 1.0.0 con `Retry-After`. `errors.ts` muestra el `detail`
  («Demasiados intentos fallidos…»), pero no usa la espera. **Semana 9:** además,
  CORS no exponía `Retry-After`, así que un cliente en navegador no podía leerla
  aunque quisiera. Corregido en la Gateway (`expose_headers`) con regresión en
  `tests/test_cabeceras_cliente_movil.py`; falta que el frontend la use.
- **O-03 — Cancelación repetida.** El contrato distingue `201` (creada) de `200`
  (ya existía). El frontend no los distingue; tras la corrección de D-01 no
  afecta, porque vuelve a pedir la orden en ambos casos.

## 5. Qué no se verificó en vivo

| Llamadas | Motivo | Cobertura existente |
|---|---|---|
| `PresupuestoService.*` (MS3) | Necesitan datos en MS3 y la coordinación MS3 → MS2 por HTTP, que el fixture `ecosistema` no conecta | Comparación estática de esta tarea (sin diferencias; D-02 corregida en 2.0.1) y `test_ms3_presupuestos_contratos.py` |
| `EvidenciaService.*` (MS4) | Necesitan almacenamiento S3 simulado y un verificador de órdenes | Comparación estática de esta tarea (sin diferencias) y `test_gateway_openapi_evidencias.py` (ejemplos contra respuestas reales de MS4) |
| `AuthService.listarUsuarios` | Pantalla de administración | Comparación estática (sin diferencias) |

## 6. Cómo ejecutar

```bash
cd backend
python -m pytest tests/test_contrato_consumo_real.py -v
```

Resultado esperado hoy: `29 passed`.

Si el frontend cambia lo que lee o envía, se actualiza
`gateway/contratos/consumo_web.py` en el mismo cambio. Si una diferencia se
corrige, su prueba pasa a XPASS: hay que quitarla de `_DIFERENCIAS_WEB` y
marcarla «Corregida» en este documento.
