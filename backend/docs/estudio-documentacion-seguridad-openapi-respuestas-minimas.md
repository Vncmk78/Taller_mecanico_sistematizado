# Estudio: documentación de seguridad en OpenAPI y diseño de respuestas mínimas

**Proyecto:** Taller mecánico sistematizado (INFO1156 - Clean Architecture)
**Fecha:** 2026-11-12
**Rama estudiada:** `DerisA` (base `5999a6c`)
**Ámbito:** contrato OpenAPI que publica `backend/gateway` (`openapi.py`,
`openapi_ms3.py`, `openapi_ejemplos.py`, `gateway/contratos/`,
`gateway/esquemas.py`) y los DTO de respuesta de MS1-MS4.

**Estado:** estudio documental sobre el contrato vigente. **No introduce
cambios de comportamiento ni de contrato.** Los hallazgos de la sección 7
quedan registrados y las recomendaciones de la sección 8 quedan pendientes de
decisión del equipo.

---

## 1. Objetivo y alcance

Este estudio responde dos preguntas:

1. **¿La documentación OpenAPI describe con suficiente precisión la seguridad
   del API?** Es decir, si un cliente (web, móvil o Integración IV) genera su
   código desde `/openapi.json`, ¿sabe qué operaciones exigen token, cuáles son
   públicas, qué rol se requiere y qué errores debe esperar?
2. **¿Las respuestas publicadas siguen un diseño mínimo?** Es decir, ¿cada
   respuesta expone solo los campos necesarios, sin secretos, sin detalle
   interno y con listas acotadas?

### 1.1 Qué se revisó

- El OpenAPI que la Gateway construye en `gateway/openapi.py` (75 *paths* /
  94 operaciones), incluida la parte de MS3 en `gateway/openapi_ms3.py`.
- Los esquemas de error de la Gateway (`gateway/esquemas.py`) y las respuestas
  reutilizables de `components.responses`.
- Los DTO de respuesta de MS1-MS4 que la Gateway copia en
  `gateway/contratos/` y los originales de cada microservicio.
- Los ejemplos publicados en `components.examples` y en cada operación.
- El OpenAPI propio de MS1-MS4, como contraste (no es lo que consumen los
  clientes, pero se expone si los puertos de los servicios quedan accesibles).

### 1.2 Qué no se revisó

- `frontend/` ni los clientes móviles.
- Pruebas de penetración, escaneo de dependencias o configuración de
  infraestructura.
- La corrección de los hallazgos de autorización ya registrados en
  `docs/checklist-revision-seguridad-rutas.md` (`H-01` a `H-07`): aquí se
  referencian cuando afectan a la documentación, no se repiten.
- El código de negocio de cada endpoint, salvo lo necesario para saber qué
  respuesta produce y qué campos publica.

### 1.3 Relación con estudios previos

Este documento complementa, sin duplicarlos:

- `docs/checklist-revision-seguridad-rutas.md` - revisión operación por
  operación de autenticación, rol, propiedad de recurso y validación. Sus
  hallazgos se citan como `H-0x`.
- `docs/estudio-owasp-autenticacion-control-acceso.md` - recomendaciones OWASP
  de autenticación y control de acceso. Sus hallazgos se citan como `OWASP-Hx`.
- `docs/versionado-contrato-openapi.md` - política semver y copias congeladas.
- `docs/contratos-api-gateway.md` - contrato escrito de rutas, errores y
  cabeceras.

---

## 2. Fuentes consultadas

| Fuente | Qué aporta a este estudio |
|---|---|
| **OpenAPI Specification 3.1.0** | Semántica de `security`, `securitySchemes`, `responses`, `examples` y `additionalProperties`. |
| **OWASP API Security Top 10:2023** - API1 BOLA, API3 Broken Object Property Level Authorization, API4 Unrestricted Resource Consumption, API8 Security Misconfiguration, API9 Improper Inventory Management | Riesgos que la documentación puede ocultar o revelar: exponer propiedades de más, listas sin límite, inventario incompleto o superficie interna publicada. |
| **OWASP ASVS 5.0** - V8 Authorization, V14 Data Protection | Requisitos verificables sobre autorización y minimización de datos. |
| **OWASP REST Security Cheat Sheet** y **API Security Checklist** | Buenas prácticas de contrato: errores homogéneos, sin detalle interno, con límites y validación. |
| **OpenAPI Security Scheme Object** | Diferencia entre `http`/`bearer` y `apiKey`; uso de `bearerFormat`. |

Las URL están en la sección 10.

---

## 3. Método

1. Se generó el OpenAPI real de la Gateway con `app.openapi()` y se contó el
   inventario (paths, operaciones, `security`, respuestas y esquemas). Se repitió
   el mismo conteo sobre el OpenAPI de MS1-MS4.
2. Se contrastó cada requisito de seguridad declarado con el *guard* real del
   microservicio, para no confundir "documentado" con "implementado" (eso ya lo
   cubre el checklist de rutas).
3. Se revisaron los DTO de respuesta campo por campo y se buscaron secretos
   (tokens, hashes, claves de almacenamiento, DSN, URLs internas).
4. Se revisaron los ejemplos publicados y las pruebas que los validan.
5. Los hallazgos nuevos se numeran `DOC-01` a `DOC-08` para no chocar con
   `H-0x` ni con `OWASP-Hx`.

**Estados usados:** OK Cumple - OBS Cumple con observación - GAP No cumple o
falta documentarlo.

**Reproducción del inventario** (desde `backend/`):

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -c "from gateway.main import app; d=app.openapi(); ops=[(m,p) for p,v in d['paths'].items() for m in v if m in {'get','post','put','patch','delete'}]; print(len(d['paths']), len(ops))"
# 75 94
```

---

## 4. Cómo documenta hoy la Gateway la seguridad

### 4.1 Esquema de seguridad

`construir_openapi()` declara un único esquema en
`components.securitySchemes` (`gateway/openapi.py:2026-2032`):

```json
"bearerAuth": { "type": "http", "scheme": "bearer", "bearerFormat": "JWT" }
```

Es el esquema correcto para un JWT en la cabecera `Authorization: Bearer ...`:
`type: http` + `scheme: bearer` permiten que Swagger muestre el botón
**Authorize**, y `bearerFormat: JWT` es informativo para el cliente. No se
declara `security` global: cada operación decide.

**Observación:** al no haber `security` global, la seguridad efectiva depende de
que cada operación emita su propia clave. Eso es explícito y auditable, pero una
omisión accidental no se hereda de un esquema global: la operación queda
documentada como pública (ver `DOC-02`).

### 4.2 Requisito de seguridad por operación

| Situación | Operaciones | Cómo se declara | Ejemplos |
|---|---:|---|---|
| Protegidas | 88 | `security: [{ "bearerAuth": [] }]` | `GET /api/auth/me`, `POST /api/ordenes`, `GET /api/evidencias` |
| Públicas explícitas | 2 | `security: []` | `POST /api/auth/register`, `POST /api/auth/login` |
| Sin clave `security` | 4 | Se omite la clave | `GET /`, `GET /api/health`, `GET /api/health/servicios`, `GET /api/health/servicios/{servicio}` |
| **Total** | **94** | | |

Las 88 protegidas son exactamente las operaciones que en el código exigen JWT.
Las 2 públicas explícitas son las únicas operaciones de negocio públicas por
diseño (registro y login). Las 4 sin clave son públicas de hecho (índice y
salud), pero su contrato no lo dice de forma explícita.

`tests/test_gateway_openapi.py:340-362` fija este comportamiento: compara la
lista de rutas protegidas, exige `security` en cada una, exige que el documento
no tenga `security` global y valida `bearerAuth`. Es una buena red de seguridad
contra omisiones.

### 4.3 Respuestas `401` y `403`

- **`401`:** está documentado en las 89 operaciones que pueden devolverlo (88
  protegidas + login). Las 88 protegidas documentan además la cabecera
  `WWW-Authenticate: Bearer` (`gateway/openapi.py:443-451`), que es lo que exige
  RFC 9110.
- **`403`:** está documentado en **68 de 94** operaciones. De las 88 protegidas,
  **21 no lo declaran**. La mayoría no puede devolverlo porque no exigen un rol
  concreto (solo JWT válido y visibilidad por recurso, que responde `404`), pero
  hay un caso que sí puede y no está documentado (ver `DOC-01`).
- **`429`:** solo el login lo declara, con `Retry-After`
  (`gateway/openapi.py:1987-1996`). Coincide con el único bloqueo por cuenta que
  existe hoy (`H-04`).

Los cuerpos de `401` y `403` son uniformes: `{"detail": "..."}` con
`ErrorDetalle` (`shared/errores_auth.py:17-26`). El mensaje no revela la causa
(token ausente, expirado o inválido reciben el mismo texto).

### 4.4 Respuestas reutilizables y ejemplos

`components.responses` publica cinco respuestas que se repiten:

| Respuesta | Estado | Uso |
|---|---|---|
| `NoAutenticado` | 401 | Falta el token, expiró o la firma no es válida |
| `ErrorInterno` | 500 | Error no controlado de la Gateway o respuesta no JSON |
| `ServicioNoDisponible` | 502 | El microservicio no respondió |
| `GatewaySaturada` | 503 | Pool de conexiones de la Gateway agotado |
| `TiempoAgotado` | 504 | El microservicio tardó demasiado |

Además hay **36 ejemplos nombrados** en `components.examples` (`error_*`,
`detalle_*` y ejemplos de operación), y las pruebas
`tests/test_gateway_openapi_ejemplos.py` validan que el documento sea OpenAPI
válido y que los ejemplos no contengan URLs internas ni tokens reales. El token
de ejemplo es visiblemente ficticio
(`eyJhbGciOiJIUzI1NiJ9.ejemplo.firma`, `gateway/openapi_ejemplos.py:53`) y está
anotado como tal en la descripción (`openapi_ejemplos.py:560-564`).

**Observación:** 181 cuerpos de respuesta usan `oneOf` para admitir el formato
de la Gateway (`ErrorRespuesta`) o el del microservicio (`ErrorDetalle`). Es
correcto porque el error puede originarse en cualquiera de los dos, pero obliga
al cliente a discriminar la forma antes de leer `detail`. Se puede mitigar con
un campo discriminante o con una descripción explícita por respuesta.

### 4.5 Cobertura y sincronización con los servicios

La documentación cubre **todas** las operaciones de negocio de MS1-MS4: 96
respuestas `2xx` tienen esquema y **0** respuestas de éxito quedan sin `content`
(excluyendo los cinco `204`). Esto se sostiene con pruebas:

- `test_cada_endpoint_de_los_cuatro_microservicios_esta_documentado` compara el
  OpenAPI de la Gateway con el real de los cuatro servicios y falla si sobra o
  falta un endpoint.
- Otras pruebas comparan campos y obligatoriedad de los contratos copiados en
  `gateway/contratos/` con los modelos de MS1-MS4.
- `test_gateway_openapi_version_estable.py` protege la copia congelada.

El punto débil no es la cobertura, sino el **contenido** de algunos esquemas
(secciones 6 y 7).

### 4.6 El contrato de los microservicios, si se exponen sus puertos

La Gateway es el contrato que consumen los clientes. Pero cada servicio también
publica su propio `/openapi.json`:

| Servicio | Paths | Operaciones | `info.version` | Esquema de seguridad |
|---|---:|---:|---|---|
| Gateway | 75 | 94 | 3.0.0 | `bearerAuth` (con `bearerFormat: JWT`) |
| MS1 | 20 | 21 | 0.1.0 | `HTTPBearer` (sin `bearerFormat`) |
| MS2 | 28 | 35 | 0.1.0 | `HTTPBearer` (sin `bearerFormat`) |
| MS3 | 31 | 41 | 0.1.0 | `HTTPBearer` (sin `bearerFormat`) |
| MS4 | 6 | 7 | 0.1.0 | `HTTPBearer` (sin `bearerFormat`) |

Si los puertos 8001-8004 quedan accesibles (lo que ya se advierte en `H-02`),
existen **dos contratos distintos** para la misma API: nombre de esquema
diferente, `bearerFormat` ausente en los servicios y versiones que no siguen la
política semver del contrato de la Gateway. Además, MS1 y MS2 publican sus rutas
`/interno/*` en su propio OpenAPI:

- MS1: `/interno/eventos/ordenes/estado`, `/interno/eventos/ms3/aviso`, etc.
- MS2: `/interno/notificaciones/ordenes/{orden_id}/destinatario`.

Esas rutas exigen un token de servicio (`X-Service-Token`) que el documento
modela como un **parámetro de cabecera**, no como un esquema de seguridad
`apiKey`. El efecto es que en `/docs` parecen operaciones sin seguridad, aunque
en ejecución el HMAC las rechaza. No expone el secreto, pero sí el mecanismo y
el inventario interno.

---

## 5. Checklist de seguridad de la documentación OpenAPI

| # | Control esperado en el contrato | Estado | Evidencia | Hallazgo |
|---|---|---|---|---|
| 1 | Esquema de seguridad declarado y correcto (`bearerAuth`) | OK | `openapi.py:2026-2032` | - |
| 2 | Cada operación protegida declara `security` | OK | 88/88; prueba `test_gateway_openapi.py:340-348` | - |
| 3 | Las operaciones públicas lo dicen explícitamente (`security: []`) | OBS | 2/6 públicas explícitas; 4 sin clave | `DOC-02` |
| 4 | `401` documentado donde puede ocurrir | OK | 89/89 | - |
| 5 | `401` incluye `WWW-Authenticate: Bearer` | OBS | 88/89 (falta login) | `DOC-03` |
| 6 | `403` documentado donde hay guard de rol | OBS | 68/94; 1 caso real sin documentar | `DOC-01` |
| 7 | `429` y `Retry-After` documentados donde hay límite | OK | Login, único límite existente | `H-04` (falta rate limiting, no documentación) |
| 8 | Errores homogéneos y sin detalle interno | OK | `ErrorRespuesta`/`ErrorDetalle`; `request_id` | - |
| 9 | `422` tipado y consumible por el cliente | GAP | `detail` como `string` o `array<object>` genérico | `DOC-04` |
| 10 | Respuestas de éxito modeladas | OK | 96 con esquema; 5 `204` sin cuerpo | - |
| 11 | Esquemas de respuesta cerrados (`additionalProperties`) | OBS | 67/113 objetos sin declararlo | `DOC-05` |
| 12 | Listas acotadas (paginación o límite) | GAP | 10 colecciones sin `limit`/`offset` | `DOC-06` |
| 13 | Sin secretos ni URLs internas en esquemas y ejemplos | OK | Tokens ficticios, sin claves de almacenamiento; prueba de ejemplos | - |
| 14 | Un solo contrato para los clientes | OBS | Gateway 3.0.0 vs servicios 0.1.0 y `HTTPBearer` | `DOC-07` |
| 15 | Inventario y cifras del contrato actualizados en la documentación | OBS | `contratos-api-gateway.md` dice 71 operaciones (hoy 94) | `DOC-08` |

---

## 6. Diseño de respuestas mínimas

### 6.1 Criterio usado

Una respuesta es "mínima" cuando cumple los cinco puntos siguientes:

1. **Necesidad:** cada campo lo usa al menos un flujo del cliente.
2. **No secretos:** no viajan tokens de terceros, hashes, claves de
   almacenamiento, credenciales, DSN ni URLs internas.
3. **No detalle interno:** los errores no revelan SQL, trazas, nombres de tablas
   ni la causa exacta del rechazo.
4. **Acotada:** las colecciones tienen límite o paginación explícita.
5. **Tipada:** el contrato declara la forma completa; el cliente no tiene que
   adivinar campos ni tipos.

### 6.2 Lo que ya está bien

| Respuesta | Campos publicados | Qué **no** publica | Evidencia |
|---|---|---|---|
| `UsuarioRespuesta` | `id`, `email`, `full_name`, `roles`, `is_active` | Hash de contraseña, intentos fallidos, bloqueo | `ms1_auth/schemas/auth.py:39-45`, `gateway/contratos/auth.py:112` |
| `TokenRespuesta` | `access_token`, `token_type`, `user` | Refresh token, secreto, expiración interna | `ms1_auth/schemas/auth.py` |
| `DispositivoRespuesta` | `dispositivo_id`, `plataforma`, `activo`, fechas | **Token FCM/APNs** del dispositivo | `ms1_auth/schemas/entrega_notificacion.py:1,15-21` |
| `EntregaRespuesta` | Estado, intentos, `ultimo_error`, historial | Respuesta cruda del proveedor, credenciales | `ms1_auth/services/entregas_notificaciones.py:168,185` |
| `EvidenciaRespuesta` | Metadatos de la evidencia | **`clave_objeto`** (ruta en MinIO) y `sha256` | `ms4_evidencias/schemas/evidencia.py:56-60` |
| `UrlDescargaRespuesta` | `url`, `expira_en` | Ruta interna, credenciales de almacenamiento | `gateway/contratos/evidencias.py:107-119` |
| Errores de la Gateway | `detail`, `error.codigo`, `estado`, `ruta`, `request_id` | SQL, DSN, trazas, nombre del servicio interno | `gateway/esquemas.py:11-28` |
| Errores de los servicios | `detail` | Causa exacta del fallo de autenticación | `shared/errores_auth.py:17-26` |

También es correcta la decisión de no publicar el `token` del dispositivo
(`DispositivoRespuesta`) ni la clave del objeto en MinIO
(`EvidenciaRespuesta`): son datos que solo necesita el servidor. El campo
`ultimo_error` de entregas guarda un **código controlado** (`proveedor_no_configurado`,
`error_de_canal`, etc.), no el mensaje del proveedor, y el código lo comenta
explícitamente (`entregas_notificaciones.py:168`).

Los datos personales que sí se publican (`email`, `full_name`, `telefono`,
`patente`) son necesarios para las pantallas de la cuenta, el perfil y los
vehículos; no se detectó ningún campo personal que sobre.

### 6.3 Brechas de minimización

1. **Listas sin límite (`DOC-06`).** Una respuesta mínima no solo evita campos
   de más: también evita devolver un número ilimitado de registros. Hay diez
   colecciones cuyo contrato no declara `limit` ni `offset`.
2. **`422` sin forma (`DOC-04`).** El detalle de validación se publica como
   `array` de objetos genéricos: el cliente no puede tipar `loc`, `msg` ni
   `type`, y termina mostrando el JSON crudo.
3. **Objetos abiertos (`DOC-05`).** Sesenta y siete esquemas de objeto no
   declaran `additionalProperties`. Un cliente estricto no puede saber si un
   campo nuevo es parte del contrato o un error.
4. **`403` faltante (`DOC-01`).** No es un problema de datos, pero sí de
   contrato de error: el cliente no puede distinguir "no tienes permiso" de
   otros fallos y puede mostrar un mensaje equivocado.

---

## 7. Hallazgos

### DOC-01 - `GET /api/presupuestos/{presupuesto_id}/envio-inicial` no documenta su `403` - **Media**

**Qué pasa.** La operación exige rol Administrador
(`ms3_presupuestos/routers/presupuestos.py:435-440`,
`dependencies=[Depends(_solo_administrador)]`), pero su entrada del OpenAPI no
declara `403`; solo `401`, `404`, `500`, `502`, `503` y `504`. Es el único caso
de las 21 operaciones protegidas sin `403` en el que el guard sí puede
devolverlo.

**Impacto.** Un cliente generado desde el contrato no tiene un tipo ni un
mensaje previsto para ese `403`; puede tratarlo como error inesperado o mostrar
el mensaje genérico. No es un fallo de autorización (el guard funciona), es un
fallo de contrato.

**Recomendación.** Añadir `"403": "Se requiere rol Administrador"` a
`errores_ms` de esa operación en `gateway/openapi.py` y una aserción en
`tests/test_gateway_openapi.py`. Es un cambio de documentación, no de
comportamiento.

**Estado.** No corregido: este documento solo registra el hallazgo.

### DOC-02 - Cuatro operaciones públicas omiten `security` en lugar de declarar `security: []` - **Baja**

**Qué pasa.** `GET /`, `GET /api/health`, `GET /api/health/servicios` y
`GET /api/health/servicios/{servicio}` no tienen la clave `security`. Las otras
dos operaciones públicas (`register` y `login`) sí declaran `security: []`.

**Impacto.** Hoy el resultado es equivalente (no hay `security` global). El
riesgo aparece si en el futuro se declara un `security` global: esas cuatro
operaciones lo heredarían y pasarían a documentarse como protegidas, o el
cliente dejaría de enviar el token en un healthcheck. También complica una
auditoría automática que solo mire la clave.

**Recomendación.** Emitir `security: []` en las cuatro operaciones y ajustar la
prueba que hoy exige que la clave no exista en tres de ellas
(`tests/test_gateway_openapi.py:359-362`).

**Estado.** No corregido.

### DOC-03 - El `401` del login no documenta `WWW-Authenticate` - **Baja**

**Qué pasa.** El login real acompaña su `401` con `WWW-Authenticate: Bearer`
(`ms1_auth/routers/auth.py:123` usa `error_no_autenticado`, que añade la
cabecera en `shared/errores_auth.py:28-34`), pero el OpenAPI no la declara
porque `_operacion` solo agrega la cabecera cuando `requiere_auth=True`
(`gateway/openapi.py:443-451`).

**Impacto.** El contrato es más pobre que la implementación. Un cliente que
genere su manejo de `401` desde el documento no sabrá que debe esperar esa
cabecera en login.

**Recomendación.** Documentar la cabecera también en el `401` de login. Se puede
hacer con un parámetro explícito en `_operacion` (por ejemplo
`documentar_www_authenticate=True`) sin cambiar el comportamiento.

**Estado.** No corregido.

### DOC-04 - El `422` publica `detail` como `string` o `array<object>` genérico - **Media**

**Qué pasa.** `ErrorDetalle` (`gateway/openapi.py:1944-1957`) define:

```json
"detail": {
  "oneOf": [
    { "type": "string" },
    { "type": "array", "items": { "type": "object" } }
  ]
}
```

El `array` no declara la forma del ítem. En la práctica es el formato de
validación de Pydantic/FastAPI (`loc`, `msg`, `type`, `input`, `ctx`), pero el
contrato no lo dice.

**Impacto.** El cliente no puede tipar el error de validación ni saber si `loc`
es una lista de strings y enteros. Los generadores de clientes crean
`List[object]` y el frontend termina mostrando el JSON sin estructura. Afecta a
todas las operaciones con cuerpo o parámetros validados.

**Recomendación.** Declarar un esquema `ErrorValidacion` con
`loc: array<string|integer>`, `msg: string`, `type: string` e `input` opcional, y
referenciarlo en el `422`. Según `docs/versionado-contrato-openapi.md`, agregar
propiedades es **MINOR**; si el equipo interpreta que se está cambiando el tipo
del ítem, corresponde **MAJOR**. Conviene decidirlo en la revisión de contrato y,
en cualquier caso, publicarlo con la próxima versión y actualizar la copia
congelada.

**Estado.** No corregido.

### DOC-05 - 67 de 113 esquemas de objeto no declaran `additionalProperties` - **Baja**

**Qué pasa.** El contrato tiene 113 esquemas; 46 declaran
`additionalProperties: false` y 67 lo omiten. Ninguno lo declara en `true`. La
mayoría de los que lo omiten son DTO de respuesta; los DTO de entrada suelen
usar `extra="forbid"` y por eso salen cerrados.

**Impacto.** En OpenAPI, omitir `additionalProperties` equivale a permitir
propiedades adicionales. El documento sugiere que las respuestas son abiertas
aunque el código no agregue campos. Un cliente estricto no puede validar la
respuesta y un cambio accidental de campo no se detecta al revisar el contrato.

**Recomendación.** Definir una política única: cerrar los DTO de respuesta
(`additionalProperties: false`) o documentar explícitamente que son abiertos.
Agregar una prueba que recorra `components.schemas` y exija la política elegida.
No cambia el comportamiento del servicio; solo el contrato.

**Estado.** No corregido.

### DOC-06 - Diez colecciones se publican sin `limit` ni `offset` - **Media**

**Qué pasa.** Estas operaciones devuelven una lista y no declaran parámetros de
paginación:

| Operación | Alcance | Observación |
|---|---|---|
| `GET /api/auth/usuarios` | Administrador | Devuelve **todos** los usuarios (`listar_usuarios(db)` sin límite) |
| `GET /api/vehiculos` | Cliente / Administrador | El Administrador recibe todo el parque vehicular (`listar_vehiculos_taller`) |
| `GET /api/vehiculos/asignados` | Mecánico | Todos los vehículos con órdenes asignadas |
| `GET /api/ordenes` | Según alcance | Todas las órdenes visibles (`listar_ordenes`) |
| `GET /api/ordenes/{orden_id}/historial` | Según visibilidad | Todos los cambios de estado |
| `GET /api/ordenes/{orden_id}/bitacora` | Según visibilidad | Todas las entradas de bitácora |
| `GET /api/ordenes/cancelaciones/pendientes` | Administrador | Todas las solicitudes pendientes |
| `GET /api/evidencias?orden_id=` | Según visibilidad | Todas las evidencias de la orden |
| `GET /api/notificaciones/dispositivos` | Usuario | Todos sus dispositivos |
| `GET /api/notificaciones/{id}/entregas` | Usuario | Historial de intentos, que **crece con cada reintento** |

`GET /api/inventario/alertas` sí está paginada (`PaginaAlertas` con `total` y
`umbral_general`), y no se incluye en la lista.

**Impacto.** El contrato permite respuestas arbitrariamente grandes. En
`/api/auth/usuarios` y `/api/vehiculos` (Administrador) el crecimiento es real;
en `/api/notificaciones/{id}/entregas` cada reintento agrega un registro y el
checklist §6 ya observa que los reintentos no tienen límite. El coste es de
memoria, tiempo de respuesta y tamaño de la respuesta, no de autorización.

**Recomendación.** Agregar `limit`/`offset` (o cursor) con valores por defecto y
máximos. Añadir parámetros opcionales es **MINOR**; cambiar la respuesta plana
por un sobre de página (`items`, `total`) es **MAJOR**, así que conviene
decidirlo antes de publicar. Como mínimo, documentar el tope que aplique el
servidor. Unificar además el nombre: hoy conviven `limit`/`offset` y `limite`
(`/api/notificaciones`, `/api/inventario/historial-umbral`).

**Estado.** No corregido.

### DOC-07 - Dos contratos de seguridad y rutas internas publicadas en los servicios - **Media (condicional)**

**Qué pasa.** La Gateway publica `bearerAuth` con `bearerFormat: JWT` y versión
3.0.0. Cada microservicio publica su propio OpenAPI con `HTTPBearer` (sin
`bearerFormat`) y versión 0.1.0. Además, MS1 y MS2 incluyen sus rutas
`/interno/*` en su OpenAPI, con `X-Service-Token` como parámetro de cabecera y
sin `security`, porque el HMAC no está modelado como esquema de seguridad.

**Impacto.** Si los puertos 8001-8004 se exponen (ver `H-02`), un cliente puede
descubrir dos contratos incompatibles y un inventario interno que la Gateway no
publica (`H-05`/`H-06`). El token de servicio no se filtra, pero sí su nombre y
la forma de las rutas internas.

**Recomendación.** En despliegue, publicar solo la Gateway. Si se necesita
diagnóstico, unificar el nombre del esquema (`bearerAuth`) y la versión, y
excluir `/interno/*` del OpenAPI con `include_in_schema=False`. Si se mantiene
visible, modelar el HMAC como `apiKey` en la cabecera para que el documento no
las muestre como públicas.

**Estado.** Depende de la configuración de despliegue y de una decisión de
equipo; no se tocó.

### DOC-08 - Cifras desactualizadas en la documentación escrita - **Informativa**

**Qué pasa.** `docs/contratos-api-gateway.md` afirma que la Gateway documenta
"71 operaciones"; el contrato vigente tiene 94. `docs/estudio-pruebas-contrato-clientes-web-movil.md`
declara 28 paths / 25 operaciones, un inventario anterior. El checklist de rutas
ya registra esta segunda discrepancia en su sección 6.

**Impacto.** Un lector que no abra `/openapi.json` se forma una idea incompleta
del tamaño y la superficie del API. No afecta a la ejecución ni a los clientes
generados.

**Recomendación.** Actualizar las cifras cuando se toque cada documento, o
reemplazarlas por una referencia a la sección 1.3 del checklist en lugar de
números fijos. No se corrigió en esta tarea.

**Estado.** Observación.

---

## 8. Recomendaciones priorizadas

| Prioridad | Recomendación | Resuelve | Tipo de cambio |
|---|---|---|---|
| Alta | Documentar el `403` de `GET /api/presupuestos/{id}/envio-inicial` y cubrirlo con prueba | DOC-01 | Contrato (PATCH) |
| Alta | Paginar o acotar `/api/auth/usuarios`, `/api/vehiculos` y `/api/ordenes`; luego el resto de colecciones | DOC-06 | Contrato + código (ver DOC-06) |
| Media | Tipar el `422` con un esquema de validación (`loc`, `msg`, `type`) | DOC-04 | Contrato (MINOR) |
| Media | Unificar el contrato de los servicios con el de la Gateway o dejar de publicar sus puertos/OpenAPI | DOC-07 | Despliegue + contrato |
| Baja | Declarar `security: []` en las cuatro operaciones públicas que lo omiten | DOC-02 | Contrato (PATCH) |
| Baja | Documentar `WWW-Authenticate` en el `401` de login | DOC-03 | Contrato (PATCH) |
| Baja | Definir y aplicar una política de `additionalProperties` en los DTO de respuesta | DOC-05 | Contrato (precisión) + prueba |
| Informativa | Actualizar las cifras de operaciones en `contratos-api-gateway.md` y en el estudio de pruebas de contrato | DOC-08 | Documentación |

**Nota de compatibilidad.** Ninguna recomendación cambia el comportamiento de
las rutas. Las que modifican el contrato deben seguir
`docs/versionado-contrato-openapi.md`: las precisiones y adiciones opcionales
van en `MINOR`; las que quitan o vuelven obligatorio algo van en `MAJOR`. Antes
de publicar, actualizar la copia congelada en `docs/openapi/` y las pruebas de
contrato.

---

## 9. Verificación realizada

**Conteos del contrato** (desde `backend/`, con `PYTHONPATH` en la raíz del
backend):

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -c "from gateway.main import app; d=app.openapi(); print(d['openapi'], d['info']['version'])"
# 3.1.0 3.0.0

.\.venv\Scripts\python.exe -c "from gateway.main import app; d=app.openapi(); ops=[(m,p) for p,v in d['paths'].items() for m in v if m in {'get','post','put','patch','delete'}]; print(len(d['paths']), len(ops))"
# 75 94
```

Resultados comprobados:

- 88 operaciones protegidas, 2 públicas explícitas, 4 sin clave `security`.
- 89 respuestas `401` documentadas; 88 con `WWW-Authenticate`.
- 68 operaciones con `403` documentado; 21 protegidas sin él (1 hueco real).
- 96 respuestas `2xx` con esquema; 5 respuestas `204` sin cuerpo.
- 113 esquemas: 46 con `additionalProperties: false`, 67 sin declararlo, 0 en
  `true`; 10 sin `required` (DTO de entrada y `HTTPValidationError`).
- 5 respuestas reutilizables; 36 ejemplos nombrados.
- 181 cuerpos de respuesta con `oneOf`.
- OpenAPI de MS1-MS4: 20/28/31/6 paths, 21/35/41/7 operaciones, versión 0.1.0 y
  esquema `HTTPBearer`.

**Pruebas del proyecto** (desde `backend/`):

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m pytest tests/test_gateway_openapi.py tests/test_gateway_openapi_ejemplos.py tests/test_gateway_openapi_evidencias.py tests/test_gateway_openapi_version_estable.py -q
```

Resultado: **159 passed en 35,46 s** (solo advertencias de deprecación de
Starlette, sin relación con el contrato).

No se modificó código, contrato ni pruebas. Los scripts de conteo se ejecutaron
fuera del repositorio (carpeta temporal) y no se agregaron al proyecto.

---

## 10. Referencias

- OpenAPI Specification 3.1.0 - https://spec.openapis.org/oas/v3.1.0
- OpenAPI Security Scheme Object - https://spec.openapis.org/oas/v3.1.0#security-scheme-object
- OWASP API Security Top 10:2023 - https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- OWASP ASVS 5.0 - https://owasp.org/www-project-application-security-verification-standard/
- OWASP REST Security Cheat Sheet - https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- OWASP API Security Cheat Sheet - https://cheatsheetseries.owasp.org/cheatsheets/API_Security_Cheat_Sheet.html
- Documentos del proyecto:
  - `docs/contratos-api-gateway.md` - contrato escrito de rutas y errores.
  - `docs/versionado-contrato-openapi.md` - semver y copias congeladas.
  - `docs/checklist-revision-seguridad-rutas.md` - hallazgos `H-01` a `H-07`.
  - `docs/estudio-owasp-autenticacion-control-acceso.md` - hallazgos
    `OWASP-H1` a `OWASP-H6`.
- Código citado:
  - `gateway/openapi.py`, `gateway/openapi_ms3.py`,
    `gateway/openapi_ejemplos.py`, `gateway/esquemas.py`,
    `gateway/contratos/`.
  - `shared/errores_auth.py`.
  - `services/ms1_auth/schemas/{auth,entrega_notificacion}.py`,
    `services/ms1_auth/services/entregas_notificaciones.py`.
  - `services/ms3_presupuestos/routers/presupuestos.py`.
  - `services/ms4_evidencias/schemas/evidencia.py`.
  - `tests/test_gateway_openapi.py`, `tests/test_gateway_openapi_ejemplos.py`,
    `tests/test_gateway_openapi_evidencias.py`,
    `tests/test_gateway_openapi_version_estable.py`.
