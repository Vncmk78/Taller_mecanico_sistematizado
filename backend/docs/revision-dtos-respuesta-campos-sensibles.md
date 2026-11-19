# Revisión: DTO de respuesta y campos sensibles o innecesarios

**Proyecto:** Taller mecánico sistematizado (INFO1156 - Clean Architecture)
**Fecha:** 2026-11-17
**Rama revisada:** `DerisA` (base `06ead4c`)
**Ámbito:** DTO de respuesta publicados por la Gateway (`gateway/contratos/`,
`gateway/openapi.py`, `gateway/esquemas.py`) y por los cuatro microservicios
(`services/ms1_auth`, `ms2_taller`, `ms3_presupuestos`, `ms4_evidencias`).

**Estado:** revisión con **un cambio de comportamiento** (`RES-01`, corregido en
MS1); los otros cuatro hallazgos quedan como recomendación. No se quitó ningún
campo de un DTO de respuesta.

---

## 1. Objetivo y alcance

La revisión responde dos preguntas:

1. **¿Alguna respuesta publica un dato sensible?** Contraseñas, hashes, tokens
   de dispositivo, claves de almacenamiento, secretos entre servicios, DSN o
   detalle interno de una excepción.
2. **¿Alguna respuesta publica campos que nadie consume?** Campos de auditoría,
   claves internas o marcas redundantes que podrían retirarse.

### 1.1 Qué se revisó

- Los 113 esquemas de `components.schemas` del OpenAPI de la Gateway, de los
  cuales **47** se usan como cuerpo de respuesta de alguna operación.
- Las **94 operaciones** publicadas sobre **75 rutas**.
- Las copias de contrato de `backend/gateway/contratos/*.py` y los DTO reales
  de `backend/services/*/schemas/*.py`.
- Lo que el frontend web lee de verdad en
  `frontend/src/infrastructure/api/*.ts` (solo lectura; no se modificó).
- Los `422` reales de MS1, porque el detalle de validación también es una
  respuesta publicada.

### 1.2 Qué no se revisó

- La app móvil (no está en este repositorio). Su consumo se conoce solo por
  `gateway/contratos/integracion_iv.py` (operaciones, **no campos**) y por
  `docs/ejemplos-contrato-movil.md`.
- El frontend como código a modificar. Solo se leyó para saber qué campos usa.
- Los cuerpos de **entrada**. La revisión es de DTO de **respuesta**; los
  secretos en entrada solo se consideran cuando una respuesta los refleja.

### 1.3 Relación con estudios previos

Completa la sección 6 de
[`estudio-documentacion-seguridad-openapi-respuestas-minimas.md`](estudio-documentacion-seguridad-openapi-respuestas-minimas.md),
que ya había verificado la exclusión de secretos y dejó abiertas las brechas
`DOC-01` a `DOC-08`. Aquí se baja al detalle de campo y se agrega un hallazgo
nuevo que ese estudio no cubría: el `422` de Pydantic refleja los valores
recibidos.

---

## 2. Método

1. Se generó el OpenAPI real de la Gateway (`app.openapi()`) y se extrajeron los
   esquemas usados en `responses.200/201`.
2. Se escanearon los nombres de campo con un patrón de riesgo:
   `password`, `pwd`, `hash`, `secret`, `token`, `clave`, `sha`, `dsn`,
   `connection`, `credencial`, `api_key`, `fcm`, `minio`, `bucket`, `uri`,
   `intento`, `bloqueo`, `salt`, `firma`, `hmac`.
3. Cada campo publicado se contrastó con:
   - `gateway/contratos/consumo_web.py` (declaración del consumidor web), y
   - las interfaces `*Api` del frontend, que son la fuente de esa declaración.
4. Se probaron los `422` reales de `POST /auth/register`, `POST /auth/login` y
   `POST /notificaciones/dispositivos`.
5. Cada campo se clasificó como **necesario**, **tolerado** (auditoría o
   conveniencia) o **candidato a retirar**, con la evidencia de quién lo lee.

---

## 3. Inventario de respuestas

| Servicio | Esquemas de respuesta principales |
|---|---|
| MS1 | `UsuarioRespuesta`, `TokenRespuesta`, `PerfilCliente*`, `NotificacionRespuesta`, `DispositivoRespuesta`, `EntregaRespuesta`, `Evento*` (rutas `/interno/*`) |
| MS2 | `OrdenRespuesta`, `EntregaOrdenRespuesta`, `DevolucionOrdenRespuesta`, `HistorialEstadoRespuesta`, `BitacoraRespuesta`, `SolicitudCancelacionRespuesta`, `SolicitudNuevaAtencionRespuesta`, `VehiculoRespuesta`, `CupoDiarioIngresosRespuesta`, `CapacidadMecanicoRespuesta` |
| MS3 | `PresupuestoDetalle`, `VersionDetalle`, `ItemSalida`, `DecisionSalida`, `RepuestoSalida`, `ProveedorSalida/Detalle`, `MovimientoSalida`, `StockSalida`, `UmbralGeneralSalida`, `CambioUmbral`, `ResultadoMovimiento`, `ResultadoReserva`, `ResultadoOperacionOrden`, `RechazoStock` |
| MS4 | `EvidenciaRespuesta`, `UrlDescargaRespuesta` |
| Gateway | `ErrorRespuesta`, `DetalleError`, `HTTPValidationError`, `ValidationError` |

Cifras del contrato vigente: **75 rutas**, **94 operaciones**, **113 esquemas**,
**47 esquemas usados como respuesta**.

---

## 4. Campos sensibles

### 4.1 Lo que ya está bien

| DTO | Campos publicados | Lo que **no** publica | Evidencia |
|---|---|---|---|
| `UsuarioRespuesta` | `id`, `email`, `full_name`, `roles`, `is_active` | Hash de contraseña, intentos fallidos, bloqueo | `ms1_auth/schemas/auth.py:39-45` |
| `TokenRespuesta` | `access_token`, `token_type`, `user` | Refresh token, secreto de firma | `ms1_auth/schemas/auth.py:47-54` |
| `DispositivoRespuesta` | `dispositivo_id`, `plataforma`, `activo`, fechas | Token FCM/APNs | `ms1_auth/schemas/entrega_notificacion.py:14-21` |
| `EvidenciaRespuesta` | Metadatos de la evidencia | `clave_objeto` (ruta en MinIO) y `sha256` | `ms4_evidencias/schemas/evidencia.py` |
| `UrlDescargaRespuesta` | `url`, `expira_en` | Ruta interna y credenciales de almacenamiento | `gateway/contratos/evidencias.py` |
| Errores de la Gateway | `detail`, `error.codigo`, `estado`, `ruta`, `request_id` | SQL, DSN, trazas, nombre del servicio interno | `gateway/esquemas.py:11-28` |

Los datos personales que sí se publican (`email`, `full_name`, `telefono`,
`patente`) son necesarios para las pantallas de cuenta, perfil y vehículos.

### 4.2 RES-01 — El `422` de validación reflejaba la contraseña y el token — **Alta (corregido)**

**Qué pasaba.** FastAPI responde `422` con el detalle de Pydantic, y cada error
incluye el valor recibido en `input`. En MS1 ese valor puede ser la contraseña
del registro/login o el token del dispositivo. La Gateway reenvía el `422` tal
cual al cliente (`gateway/routers/proxy.py`, decisión 3), así que el secreto
viajaba en el cuerpo de la respuesta y quedaba expuesto a cualquier registro
intermedio que guarde cuerpos (APM, proxy inverso o un cliente que los registre).

Evidencia real obtenida con el `TestClient` de MS1 **antes** de la corrección:

```json
// POST /auth/register  {"password": "abc123", ...}
{"detail":[{"type":"string_too_short","loc":["body","password"],
            "msg":"String should have at least 8 characters",
            "input":"abc123","ctx":{"min_length":8}}]}

// POST /auth/login  {"password": "MiClaveReal123"}
{"detail":[{"type":"missing","loc":["body","email"],"msg":"Field required",
            "input":{"password":"MiClaveReal123"}}]}

// POST /notificaciones/dispositivos  {"token": "token-fcm-corto", ...}
{"detail":[{"type":"too_short","loc":["body","token"],
            "input":"token-fcm-corto","ctx":{"min_length":20,...}}]}
```

**Causa raíz.** El DTO de error (`ValidationError`) publica `input` y `ctx`, y
el manejo por defecto de FastAPI no distingue campos secretos. Afecta a
`RegistroClienteSolicitud.password` (`schemas/auth.py:16`),
`LoginSolicitud.password` (`schemas/auth.py:24`) y
`DispositivoRegistrar.token` (`schemas/entrega_notificacion.py:11`).

**Corrección aplicada.** En `services/ms1_auth/main.py` se registra un manejador
de `RequestValidationError` que enmascara los valores de los campos secretos
(`password`, `token`, `contrasena`, `secreto`, `secret`) y conserva el resto del
detalle (`type`, `loc`, `msg`, `ctx`). No cambia el esquema publicado: `input`
sigue siendo opcional; solo deja de reflejar secretos.

```json
{"detail":[{"type":"string_too_short","loc":["body","password"],
            "msg":"String should have at least 8 characters",
            "input":"***","ctx":{"min_length":8}}]}
```

Solo MS1 recibe credenciales o tokens en el cuerpo. MS2, MS3 y MS4 no tienen
campos secretos en sus DTO de entrada, así que no se tocaron.

**Pendiente de decisión.** Lo más estricto sería **eliminar `input` y `ctx`**
del contrato de `422` (relacionado con `DOC-04`). Eso sí es un cambio de
contrato: según [`versionado-contrato-openapi.md`](versionado-contrato-openapi.md)
§2, quitar un campo es **MAJOR** y debe coordinarse con web e Integración IV.
Con el enmascarado actual el `422` mantiene la forma y no se rompe ningún
cliente.

**Prueba de regresión.** `tests/test_credenciales_vacias_y_multirol.py`:
`test_el_422_no_devuelve_la_contrasena_enviada` verifica que la contraseña corta
del registro y la contraseña enviada sin email no aparecen en la respuesta.

---

## 5. Campos innecesarios

### 5.1 Criterio aplicado

No se retira un campo solo porque el frontend web no lo lea. El contrato lo
comparten web, la app móvil y los scripts de integración; además, varios campos
de auditoría son requisito de negocio. Para retirar un campo hace falta
**evidencia de que ningún consumidor lo usa**. Esa evidencia hoy no existe para
la mayoría de los candidatos, y la declaración web es parcial (ver `RES-02`).

### 5.2 RES-02 — La declaración de consumo web es parcial — **Media**

`gateway/contratos/consumo_web.py` declara **42 llamadas** y su encabezado dice
«Lo que no aparece aquí, el frontend no lo usa». El frontend tiene **71
llamadas** en sus servicios (sin contar pruebas). Faltan servicios completos:

| Servicio del frontend | Llamadas sin declarar | Campos que lee y **no** están en `CONSUMO_WEB` |
|---|---|---|
| `InventarioService.ts` | 12 | `clave_operacion` (l. 100), `registrado_por_id` (l. 107), `vigente_desde` (l. 139), `actualizado_por_id` (l. 140), `administrador_id` (l. 150) |
| `RepuestoService.ts` | 5 | `umbral_particular`, `umbral_efectivo`, `bajo_umbral`, `proveedor_tipo_distribuidor` |
| `ProveedorService.ts` | 4 | `cantidad_repuestos`, `contacto`, `tipo_distribuidor` |
| `NotificationService.ts` | 2 | `ultimo_error` y `intentos_registrados` de entregas (l. 46-52) |

Consecuencia: **ninguno de los candidatos de esta sección puede retirarse hoy
sin completar antes la declaración del consumidor**. La declaración de web es
una foto de los flujos de la Semana 8, no el inventario completo. Para la app
móvil ni siquiera existe una declaración de campos: `integracion_iv.py` declara
operaciones y roles, no campos.

**Recomendación.** Ampliar `CONSUMO_WEB` con inventario, repuestos, proveedores
y entregas, y crear una declaración de campos para móvil (equivalente a
`consumo_web.py`). Recién entonces se puede decidir un retiro con evidencia.

### 5.3 RES-03 — `VersionDetalle.vigente` duplica `version_vigente` — **Baja**

`VersionDetalle` publica `vigente: bool` (`gateway/contratos/presupuestos.py:155`)
y el resumen del presupuesto ya publica `version_vigente: int | null` (l. 170).
El frontend usa `version_vigente` (`PresupuestoService.ts:62,134`) y **no lee**
`vigente`. Es la única marca de conveniencia que se puede considerar redundante
sin depender de un cálculo oculto.

Aun así, no se retiró: la app móvil podría resaltar la versión vigente con ese
booleano, y quitarlo es un cambio **MAJOR** del contrato. Queda como candidato
para la próxima revisión mayor, después de completar `RES-02`.

### 5.4 RES-04 — IDs de auditoría publicados — **Informativa**

Las respuestas publican IDs de las personas que actuaron:

| Campo | Web lo lee | Observación |
|---|---|---|
| `orden.creado_por_id`, `devuelto_por_id`, `mecanico_actual_id` | Sí | Necesarios para las pantallas de la orden |
| `historial.actor_usuario_id` | Sí | Trazabilidad mostrada al cliente |
| `bitacora.autor_usuario_id` | Sí | Autor de la anotación |
| `solicitud.cliente_usuario_id`, `revisor_id` | Sí | Identifican al solicitante y al revisor |
| `cupo.actualizado_por_id`, `capacidad.actualizado_por_id` | Sí | Configuración del taller |
| `entrega.entregado_por_id`, `historial_id` | No | Auditoría de la entrega física; la orden ya se consulta aparte |
| `movimiento.registrado_por_id`, `umbral.actualizado_por_id`, `cambio.administrador_id` | Sí (inventario) | Auditoría de stock y umbrales |
| `cancelacion.administrador_id`, `confirmada_en` | No | Revisión administrativa de la solicitud |

No son datos sensibles (son identificadores internos, no correos ni teléfonos)
y varios son la única forma de auditar quién cambió qué. Se mantienen. Si se
quisiera una respuesta "solo de negocio", habría que crear DTO específicos por
pantalla, lo que excede esta revisión.

### 5.5 RES-05 — Contexto de notificaciones — **Informativa**

`NotificacionRespuesta` publica `vehiculo_id`, `ocurrido_en` y `leida_en` además
de lo que lee el frontend. `presupuesto_id`, `solicitud_id`, `repuesto_id` y
`orden_id` **sí** los lee la web (`NotificationService.ts:38-40`), y los tres
primeros están documentados como referencias de navegación en
[`notificaciones-canales.md`](notificaciones-canales.md) l. 66-67. Se mantienen:
el costo es un campo anulable y el beneficio es que la bandeja pueda navegar al
objeto sin una segunda consulta.

---

## 6. Recomendaciones

| Prioridad | Acción | Hallazgo | Tipo de cambio |
|---|---|---|---|
| Alta | ~~Enmascarar contraseña y token en el `422` de MS1~~ (**hecho**) | `RES-01` | Código + prueba |
| Media | Completar `CONSUMO_WEB` (inventario, repuestos, proveedores, entregas) y declarar los campos que usa la app móvil | `RES-02` | Documentación/pruebas |
| Media | Decidir si el `422` deja de publicar `input`/`ctx`; si sí, es MAJOR y se coordina | `RES-01`, `DOC-04` | Contrato |
| Baja | Evaluar el retiro de `VersionDetalle.vigente` en la próxima MAJOR | `RES-03` | Contrato |
| Informativa | Documentar que los IDs de auditoría son parte deliberada de la respuesta | `RES-04` | Documentación |

---

## 7. Verificación realizada

Desde `backend/`, con `PYTHONPATH` apuntando a `backend/`:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_credenciales_vacias_y_multirol.py \
    tests/test_gateway_openapi_version_estable.py -q
# 40 passed

.\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py \
    tests/test_canales_notificaciones.py tests/test_contrato_consumo_real.py \
    tests/test_gateway_openapi.py tests/test_gateway_openapi_ejemplos.py -q
# 206 passed
```

El contrato congelado no cambió: el esquema de `ValidationError` ya declaraba
`input` como opcional y el ejemplo real de `login 422` (cuerpo `{}`) sigue
coincidiendo byte a byte.

---

## 8. Referencias

- [`estudio-documentacion-seguridad-openapi-respuestas-minimas.md`](estudio-documentacion-seguridad-openapi-respuestas-minimas.md) — hallazgos `DOC-01` a `DOC-08`.
- [`versionado-contrato-openapi.md`](versionado-contrato-openapi.md) — reglas PATCH/MINOR/MAJOR.
- [`notificaciones-canales.md`](notificaciones-canales.md) — contexto de la bandeja.
- [`diferencias-contrato-consumo-real.md`](diferencias-contrato-consumo-real.md) — diferencia `D-01` de la cancelación.
- `backend/gateway/contratos/consumo_web.py` — declaración del consumidor web.
- `backend/services/ms1_auth/main.py` — manejador que enmascara secretos en el `422`.
- `backend/tests/test_credenciales_vacias_y_multirol.py` — prueba de regresión.
