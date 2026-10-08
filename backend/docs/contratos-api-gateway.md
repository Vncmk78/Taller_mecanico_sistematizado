# Contratos de la API Gateway — SGTM

Este documento es el contrato único que consume el frontend web (React) y la
app móvil (Integración IV). La fuente de verdad interactiva está en el Swagger
de la Gateway: <http://localhost:8000/docs> y su versión JSON en
<http://localhost:8000/openapi.json>.

Reglas que se aplican a todos los endpoints:

- La Gateway escucha en `/api/*` y reenvía al microservicio sin modificar el
  body, el query string ni la cabecera `Authorization`.
- Las respuestas exitosas y los errores de los microservicios pasan tal cual.
- El `Authorization: Bearer <token>` se obtiene en `POST /api/auth/login`.
- La cabecera opcional `X-Request-ID` permite rastrear una petición en la
  Gateway y en el microservicio; si no viene (o es inválida), la Gateway
  genera un UUID y lo devuelve en la respuesta.
- Errores propios de la Gateway: `RUTA_NO_ENCONTRADA` (404),
  `MICROSERVICIO_INALCANZABLE` (502), `TIEMPO_AGOTADO` (504),
  `GATEWAY_SATURADA` (503), `CUERPO_DEMASIADO_GRANDE` (413),
  `ERROR_MICROSERVICIO` y `ERROR_INTERNO` (500), todos con el cuerpo
  `{"detail": "...", "error": {"codigo", "estado", "ruta", "request_id"}}`.
  `GATEWAY_SATURADA`, `ERROR_MICROSERVICIO` y `CUERPO_DEMASIADO_GRANDE` son de
  la Semana 4/5 (mapeo de errores, cabeceras y límites de body).
- Límites de body por prefijo (checklist 4.2): la Gateway rechaza con `413`
  (`CUERPO_DEMASIADO_GRANDE`, mensaje genérico) los bodies mayores al límite
  del prefijo **antes de leerlos o llamar al microservicio**. El `prefijo`
  `evidencias` admite hasta 12 MiB (multipart con foto de hasta 10 MB); el
  resto de los prefijos (JSON de MS1/MS2/MS3) admite hasta 1 MiB. Un
  `Content-Length` no numérica responde `400` (`ERROR_HTTP`).
- Errores de los microservicios: `{"detail": "mensaje"}` con su status code.
  En los `422` (validación de body en MS1/MS2), `detail` es una **lista** de
  errores de FastAPI, no un string:

  ```json
  { "detail": [ { "loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error" } ] }
  ```

### Errores que vienen de los microservicios

Un 4xx/5xx que responde el microservicio **no es un error de la Gateway**:
- Si el body es **JSON** (`{"detail": ...}` de FastAPI) se reenvía **tal
  cual**, con su status code, para que el frontend siga leyendo `detail`.
- Si el body **no es JSON** (texto plano o HTML, típico de un proxy
  intermedio) se normaliza al formato común con el código
  `ERROR_MICROSERVICIO` y el mismo estado. Los `404` y `405` no-JSON usan
  `RUTA_NO_ENCONTRADA` y `METODO_NO_PERMITIDO` con sus mensajes habituales.
  `WWW-Authenticate` y `Retry-After` se conservan.

Fallo de red del proxy (no llega ninguna respuesta del microservicio):

| Excepción | Estado | Código |
|---|---|---|
| `ConnectError`, `ConnectTimeout` | 502 | `MICROSERVICIO_INALCANZABLE` |
| `ReadTimeout`, `WriteTimeout` | 504 | `TIEMPO_AGOTADO` |
| `PoolTimeout` | 503 | `GATEWAY_SATURADA` |
| Otro `RequestError` | 502 | `MICROSERVICIO_INALCANZABLE` |

### Cabeceras de la respuesta

La Gateway reenvía las cabeceras que manda el microservicio
(`WWW-Authenticate`, `Content-Disposition`, `Cache-Control`, `Set-Cookie`,
`Retry-After`, …), excepto las de conexión (*hop-by-hop*), `Content-Length`,
`Content-Encoding`, `Server`, `Date`, `X-Request-ID` (lo pone la Gateway) y
las `Access-Control-*` (el CORS lo resuelve la Gateway). Un `Location` que
apunte a la URL interna del microservicio (por ejemplo la redirección 307 de
FastAPI por la barra final) se traduce a la URL pública de la Gateway con
`/api`: `http://localhost:8002/vehiculos` → `https://<gateway>/api/vehiculos`.

## Swagger y OpenAPI (`/docs`)

La fuente interactiva del contrato es <http://localhost:8000/docs> y su versión
JSON es <http://localhost:8000/openapi.json>. Además de los esquemas, el esquema
publica **un ejemplo real por body y por respuesta**, para que el frontend y la
app móvil puedan copiar un payload sin inventarlo.

### Respuestas reutilizables

`components.responses` publica las respuestas que se repiten en todas las
operaciones, con su cabecera `X-Request-ID` y sus ejemplos:

| Respuesta | Estado | Cuándo se usa |
|---|---|---|
| `NoAutenticado` | 401 | Falta el token, expiró o su firma no es válida (documenta `WWW-Authenticate: Bearer`) |
| `ErrorInterno` | 500 | Error no controlado de la Gateway (`ERROR_INTERNO`) o respuesta no JSON (`ERROR_MICROSERVICIO`) |
| `ServicioNoDisponible` | 502 | El microservicio no respondió |
| `GatewaySaturada` | 503 | El pool de conexiones de la Gateway está agotado |
| `TiempoAgotado` | 504 | El microservicio tardó demasiado |

El `503` y el `504` de cada operación de negocio se referencian con `$ref` a
`GatewaySaturada` y `TiempoAgotado`. Excepción: en `/api/evidencias*` el `503`
también puede venir de MS4 (almacenamiento o MS2 caídos), así que se describe en
línea con ambos formatos y sus ejemplos. El `401`, el `500` y el `502` se describen en
línea en cada operación porque no son idénticos en todas: dependen de si el error
lo genera la Gateway (`ErrorRespuesta`) o el microservicio (`ErrorDetalle`), y el
OpenAPI publica en cada caso el esquema que corresponde.

### Ejemplos nombrados

`components.examples` guarda los cuerpos reales, referenciables por nombre desde
`openapi.json`:

| Prefijo | Ejemplos |
|---|---|
| `error_*` | Los ocho errores de la Gateway: `error_ruta_no_encontrada` (404), `error_metodo_no_permitido` (405), `error_cuerpo_demasiado_grande` (413), `error_interno_gateway` (500), `error_microservicio` (respuesta no JSON), `error_microservicio_no_disponible` (502), `error_gateway_saturada` (503) y `error_tiempo_agotado` (504) |
| `detalle_*` | Los errores que responden MS1, MS2 y MS4: token ausente, token inválido, credenciales incorrectas, rol insuficiente, vehículo inexistente, perfil Cliente ausente, correo o patente ya registrados, los dos `422` de validación y los de evidencias (orden o evidencia no encontrada, tipo de archivo no permitido, archivo vacío, almacenamiento u órdenes no disponibles) |

Los mensajes de los errores de la Gateway se importan de `gateway/errores.py`, así
que el ejemplo no puede divergir del texto que la Gateway responde realmente. Los
ejemplos de los microservicios usan los `detail` exactos de MS1 y MS2 (por ejemplo
`"No tienes permiso para realizar esta operación"` en el `403` de vehículos). Los
ejemplos de órdenes son los de `shared/openapi_ordenes.py` y se conservan sin
cambios.

Ninguna URL interna (`localhost:8001`, `localhost:8002`, …) ni token real se
publica en el esquema: el `access_token` de ejemplo es un JWT ficticio que no
habilita ninguna llamada.

### Cabecera `X-Request-ID` y health checks

Todas las respuestas bajo `/api` declaran la cabecera `X-Request-ID` en el
OpenAPI, con su descripción y su ejemplo (`abc-123`); es la misma clave que viaja
en `error.request_id`. Los dos endpoints de salud muestran también sus ejemplos:
`200` con los cuatro microservicios en `ok` y el `503` con `status: degradado`
(ver la sección siguiente).

### Verificación

```bash
python -m pytest tests/test_gateway_openapi.py tests/test_gateway_openapi_ejemplos.py tests/test_gateway_openapi_evidencias.py -v
```

`tests/test_gateway_openapi_ejemplos.py` valida el documento con
`openapi-spec-validator`, comprueba que **todos** los ejemplos (incluidos los de
órdenes) cumplen el esquema que los acompaña, que no hay URLs internas ni tokens
reales y que `gateway/openapi_ejemplos.py` es idempotente. La dependencia de
desarrollo se instala con `pip install -r requirements-dev.txt`.

## Health checks (`/api/health`)

Públicos (no exigen `Authorization`) y de solo lectura: miden la salud del
sistema, no son endpoints de negocio.

### GET `/api/health`

Responde la propia Gateway, **sin consultar a los microservicios** (lo usa
Vercel y no puede depender de que estén arriba). `200` siempre que el proceso
de la Gateway esté vivo:

```json
// Response 200
{ "status": "ok", "servicio": "gateway" }
```

### GET `/api/health/servicios`

Consulta `/health/db` de los cuatro microservicios en paralelo con un timeout
de `GATEWAY_HEALTH_TIMEOUT_SECONDS` (2 s por defecto) por servicio. `200` si
todos responden; `503` si al menos uno no lo está. Toda respuesta trae
`Cache-Control: no-store`. El body no expone URLs internas.

```json
// Response 200
{
  "status": "ok",
  "gateway": "ok",
  "servicios": {
    "ms1_auth": { "estado": "ok", "latencia_ms": 3 },
    "ms2_taller": { "estado": "ok", "latencia_ms": 4 },
    "ms3_presupuestos": { "estado": "ok", "latencia_ms": 2 },
    "ms4_evidencias": { "estado": "ok", "latencia_ms": 5 }
  }
}
```

```json
// Response 503
{
  "status": "degradado",
  "gateway": "ok",
  "servicios": {
    "ms1_auth": { "estado": "ok", "latencia_ms": 3 },
    "ms2_taller": { "estado": "ok", "latencia_ms": 4 },
    "ms3_presupuestos": { "estado": "caido" },
    "ms4_evidencias": { "estado": "sin_base", "latencia_ms": 6, "codigo_http": 503 }
  }
}
```

Estados por servicio:

- `ok` — respondió `200` a `/health/db` en menos del timeout (`latencia_ms` en
  milisegundos enteros).
- `sin_base` — el proceso responde pero su health/base falla; incluye
  `codigo_http`.
- `tiempo_agotado` — superó el timeout de 2 s.
- `caido` — sin conexión (servicio apagado o no arrancado).

## Rutas de Presupuestos y Evidencias

La Gateway decide el destino por el **primer segmento** de la ruta y reenvía
el resto del camino, el query string y el body tal cual. Por eso MS3 y MS4
deben publicar sus endpoints bajo sus prefijos propios y **nunca** colgarlos
bajo `/ordenes/...`: ese prefijo resuelve a MS2.

| Prefijos | Microservicio | Ejemplo |
|---|---|---|
| `auth` | MS1 (Autenticación y Usuarios) | `/api/auth/login` → `POST /auth/login` |
| `vehiculos`, `vehiculo`, `ordenes`, `orden`, `clientes`, `mecanicos` | MS2 (Vehículos y Órdenes) | `/api/ordenes/31/mecanico` → `PUT /ordenes/31/mecanico` |
| `presupuestos`, `presupuesto`, `repuestos`, `proveedores`, `inventario` | MS3 (Presupuestos) | `/api/presupuestos` → `GET /presupuestos` |
| `evidencias`, `evidencia` | MS4 (Evidencia Multimedia) | `/api/evidencias?orden_id=31` → `GET /evidencias?orden_id=31` |

Convención que deben respetar los endpoints de la Semana 5:

- **MS4 publica todo bajo `/evidencias`**, por ejemplo `POST /evidencias`
  (subida de archivos) y `GET /evidencias?orden_id=...` (listado de una
  orden). **No existe** `GET /ordenes/{id}/evidencias`: esa ruta llegaría a
  MS2, no a MS4.
- **MS3 publica bajo sus propios prefijos**, por ejemplo
  `GET /presupuestos?orden_id=...`. Tampoco se cuelga bajo `/ordenes/...`.
- El microservicio recibe la ruta sin el prefijo `/api` (p. ej. MS4 recibe
  `/evidencias`, no `/api/evidencias`).

Nota sobre la subida de archivos: la Gateway conserva el `Content-Type` con el
`boundary` del multipart y aplica un límite de tamaño de body por prefijo
(checklist 4.2): 1 MiB para los prefijos JSON y 12 MiB para `evidencias` (foto
de hasta 10 MB + margen del multipart). Superarlo responde `413
CUERPO_DEMASIADO_GRANDE` sin llamar al microservicio. No hay streaming hacia
MS4 (riesgo 4.3 acotado por ese límite): los videos usan el flujo C (POST
prefirmado directo a MinIO, Semana 6+). Detalle en
[checklist-seguridad-evidencias.md](checklist-seguridad-evidencias.md) (4.2,
4.3 y 4.5) y `estudio-almacenamiento-objetos.md` (sección 6).

Deuda registrada (decisión pendiente): existen alias en singular
(`presupuesto`, `evidencia`, `orden`, `vehiculo`) que reenvían la ruta tal
cual, de modo que `/api/evidencia/x` llegaría a MS4 como `/evidencia/x`, una
ruta que ningún servicio expone. Se conservan por compatibilidad con MS2 (los
usa el equipo) y no se consideran contrato: MS3 y MS4 publican únicamente sus
prefijos en plural.

## Relaciones y flujo inicial de MS2

La aplicación web y la aplicación móvil consumen estas relaciones únicamente a
través de la API Gateway. No deben conectarse directamente a MS2 ni asumir que
los identificadores de MS1 tienen claves foráneas en la base de MS2.

La cadena funcional implementada hasta Semana 3 es:

`Cliente → Vehículo → Ingreso físico → Orden de trabajo → Mecánico responsable → Estado → Historial`

### Relaciones físicas dentro de MS2

Estas relaciones tienen claves foráneas porque sus tablas viven en la misma
base PostgreSQL de MS2:

| Relación | Cardinalidad y columna física |
|---|---|
| Cliente → Vehículo | `Cliente 1:N Vehiculo`; FK `vehiculo.cliente_id` |
| Vehículo → Ingreso físico | `Vehiculo 1:N IngresoVehiculo`; FK `ingreso_vehiculo.vehiculo_id` |
| Vehículo → Orden | `Vehiculo 1:N OrdenTrabajo`; FK `orden_trabajo.vehiculo_id` |
| Ingreso físico → Orden | `IngresoVehiculo 1:N OrdenTrabajo`; FK `orden_trabajo.ingreso_id` |
| Estado → Orden | `EstadoOrden 1:N OrdenTrabajo`; FK `orden_trabajo.estado_codigo` |
| Orden → HistorialEstado | `OrdenTrabajo 1:N HistorialEstado`; FK `historial_estado.orden_id` |
| Orden → HistorialAsignacion | `OrdenTrabajo 1:N HistorialAsignacion`; FK `historial_asignacion.orden_id` |
| Estado → HistorialEstado | `estado_anterior` opcional y `estado_nuevo` obligatorio apuntan al catálogo local `estado_orden` |

Un ingreso abierto puede asociarse a más de una orden cuando una nueva atención
comienza sin que el vehículo haya salido físicamente del taller. Las órdenes y
sus historiales se conservan como trazabilidad; no se borran al cancelar.

### Referencias lógicas hacia MS1

Estas columnas guardan identificadores de usuarios administrados por MS1. No
tienen ni deben tener FK física entre bases de microservicios:

| Columna de MS2 | Referencia lógica |
|---|---|
| `cliente.usuario_id` | Usuario de MS1 dueño del perfil Cliente; es único en MS2 |
| `ingreso_vehiculo.registrado_por_id` | Usuario Administrador que registró el ingreso |
| `orden_trabajo.creado_por_id` | Usuario Administrador que creó la orden |
| `orden_trabajo.mecanico_actual_id` | Usuario que actúa como responsable actual; puede ser nulo |
| `historial_asignacion.mecanico_anterior_id` / `mecanico_nuevo_id` | Responsables anterior y nuevo |
| `historial_asignacion.administrador_id` | Administrador que asignó o reasignó |
| `historial_estado.actor_usuario_id` | Usuario que originó el cambio cuando `origen=usuario` |
| `diagnostico_autor_id`, `entregado_por_id`, `devuelto_por_id` | Referencias previstas por el modelo para etapas posteriores; no tienen endpoints de Semana 3 |

La validación remota de que el `mecanico_id` existe, está activo y tiene rol
Mecánico todavía no dispone de un contrato implementado entre MS2 y MS1. El
endpoint actual conserva el identificador como referencia lógica; esta
dependencia no debe sustituirse por acceso directo a la base de MS1.

### Flujo implementado hasta Semana 3

1. Un Cliente autenticado registra uno o varios vehículos propios.
2. Un Administrador confirma el ingreso físico al crear una orden para un
   vehículo registrado. Si ya hay un ingreso abierto, se reutiliza.
3. La orden se crea en `Recibido`, sin mecánico obligatorio, junto con su
   entrada inicial de `HistorialEstado`.
4. El Administrador asigna el primer mecánico.
5. La primera asignación cambia `Recibido → Esperando diagnóstico` y registra,
   en la misma transacción, `HistorialAsignacion` e `HistorialEstado`.
6. El Administrador puede reasignar; la reasignación registra al responsable
   anterior y al nuevo, pero conserva el estado actual.
7. Repetir exactamente el mismo responsable es idempotente y no crea otro
   cambio de historial.
8. `Entregado` y `Cancelado` son estados terminales y rechazan asignaciones o
   reasignaciones.

El resto del ciclo de atención no está implementado en estos contratos. Los
ocho estados y la tabla completa de transiciones están documentados en
[`maquina-estados-ordenes.md`](maquina-estados-ordenes.md); ese documento no
autoriza por sí solo endpoints o transiciones futuras.

### Roles y visibilidad actuales

| Rol efectivo | Vehículos | Órdenes |
|---|---|---|
| Administrador | Consulta cualquiera de los vehículos del taller y puede registrarlos | Crea órdenes, ve todas, asigna o reasigna mecánicos y cambia su estado |
| Cliente | Registra, lista, consulta y modifica únicamente sus vehículos | Lista y consulta únicamente órdenes asociadas a sus vehículos; no crea órdenes |
| Mecánico | Lista sus vehículos asignados en `/api/vehiculos/asignados` y consulta los asignados a él | Lista, consulta y cambia el estado únicamente de órdenes cuyo `mecanico_actual_id` coincide con su usuario; consulta su historial |
| Multirol | Acumula los permisos de sus roles | Une los alcances Cliente y Mecánico sin duplicados; si incluye Administrador, conserva visibilidad global |

Una orden inexistente y una orden fuera del alcance del Cliente o Mecánico
responden el mismo `404`, para no revelar la existencia de recursos ajenos.
Lo mismo aplica al detalle de vehículos: el Cliente solo ve los propios y el
Mecánico solo los que tiene asignados.

## Autenticación (MS1)

### POST `/api/auth/register`

Registro público de un cliente (el rol Cliente se asigna en el servidor).

| Atributo | Descripción |
|---|---|
| Auth | No requiere |
| Body | `{"email": string, "password": string (mín. 8), "full_name": string}` |
| Respuesta OK | `201` con `UsuarioRespuesta` |
| Errores | `409` correo ya registrado · `422` datos inválidos · `404/502/500` de la Gateway |

```json
// Request
{ "email": "ana@correo.cl", "password": "clave-segura-123", "full_name": "Ana Pérez" }
// Response 201
{ "id": 7, "email": "ana@correo.cl", "full_name": "Ana Pérez",
  "roles": ["cliente"], "is_active": true }
```

### POST `/api/auth/login`

Inicia sesión y entrega el token de acceso.

| Atributo | Descripción |
|---|---|
| Auth | No requiere |
| Body | `{"email": string, "password": string}` |
| Respuesta OK | `200` con `TokenRespuesta` |
| Errores | `401` credenciales inválidas · `404/502/500` de la Gateway |

```json
// Request
{ "email": "ana@correo.cl", "password": "clave-segura-123" }
// Response 200
{ "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "bearer",
  "user": { "id": 7, "email": "ana@correo.cl", "full_name": "Ana Pérez",
            "roles": ["cliente"], "is_active": true } }
```

### GET `/api/auth/me`

Devuelve el usuario identificado por el token.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con `UsuarioRespuesta` |
| Errores | `401` JWT ausente o inválido · `404/502/500` de la Gateway |

```json
// Response 200
{ "id": 7, "email": "ana@correo.cl", "full_name": "Ana Pérez",
  "roles": ["cliente"], "is_active": true }
```

### El JWT: claims, validación y quién las aplica

Esta sección es la **fuente de verdad** del token de acceso. La implementación
que la garantiza es [`shared/auth.py`](../shared/auth.py), un módulo puro sin
FastAPI, SQLAlchemy ni conexión a base de datos, pensado para que todos los
microservicios compartan exactamente el mismo contrato. Si este documento y el
código discrepan, el código es la referencia: no se reimplementa la validación
en otro lado.

#### Claims emitidos

`POST /api/auth/login` entrega un JWT firmado con **HS256** que contiene
exactamente tres claims:

| Claim | Tipo | Obligatorio | Contenido |
|---|---|---|---|
| `sub` | `string` | Sí | El `usuario_id` de MS1 como texto **entero positivo** (`"7"`, nunca `"usr_7"`) |
| `roles` | `list[string]` | Sí | Lista **no vacía y sin duplicados** con los roles del usuario, ordenada alfabéticamente |
| `exp` | `number` | Sí | Vencimiento en epoch seconds (por defecto 60 minutos, `MS1_JWT_EXPIRE_MINUTES`) |

Los valores de `roles` solo pueden ser `cliente`, `mecanico` o `administrador`
(enum `NombreRol`). Cualquier otro valor hace que el token sea rechazado.

Deliberadamente **no** viajan `email`, `role` (singular), `nombre` ni `iat`: la
identidad se resuelve siempre contra la base de MS1 o MS2 en el momento de la
petición, de modo que un token no queda obsoleto si el usuario cambia de correo,
nombre o roles mientras el token sigue vigente. El correo y el nombre completos
se obtienen en `GET /api/auth/me`.

> **Atención al integrarse con otros módulos:** el claim es `roles` y es una
> **lista**, aunque el usuario tenga un único rol. Un cliente que lea
> `payload.role` (singular) o que asuma un string en lugar de un array obtendrá
> `undefined` y denegará el acceso a usuarios legítimos.

#### Quién valida el token

**La Gateway no valida el JWT.** Reenvía la cabecera `Authorization` al
microservicio destino sin inspeccionarla, y por eso no lee ni necesita el secreto
de firma. Cada microservicio valida por su cuenta, y lo hace siempre con
`shared.auth.validar_token_acceso`, que:

- exige `sub` y `exp` presentes (`require_sub`, `require_exp`);
- rechaza firmas inválidas y tokens expirados con el mismo error `401`;
- devuelve un `PrincipalAutenticado` con `usuario_id: int` y
  `roles: frozenset[NombreRol]`, sin tocar la base de datos;
- no acepta un `sub` no numérico, una `roles` vacía, con duplicados o con un rol
  desconocido.

La ventaja de este diseño es que la Gateway no puede falsificar una identidad ni
filtrar el token, y que el secreto de cada microservicio se mantiene en su
propio prefijo de variables (`MS1_JWT_SECRET_KEY`, `MS2_JWT_SECRET_KEY`, …).

El secreto es obligatorio, se lee solo del entorno y debe tener **al menos 32
caracteres**: `shared/auth.py` lanza `ConfiguracionJWTError` en el arranque si
falta, es corto o si el algoritmo no es `HS256`. No debe existir un valor por
defecto en el código, porque un default conocido permitiría firmar tokens
válidos.

#### Errores de autenticación y autorización

| Situación | Respuesta |
|---|---|
| Sin cabecera `Authorization`, o con un esquema distinto de `Bearer` | `401` + `WWW-Authenticate: Bearer` |
| Token con firma inválida, expirado, o con `sub`/`roles` mal formados | `401` + `WWW-Authenticate: Bearer` |
| Token válido, pero el usuario ya no existe o está inactivo | `401` |
| Token válido, pero el principal no tiene ninguno de los roles exigidos | `403` |
| Recurso inexistente **o** ajeno al principal | `404` (se usa el mismo código para no revelar la existencia de recursos de otros) |

La distinción `401` / `403` es parte del contrato: `401` significa "identifícate
otra vez" y `403` significa "identificado, pero no te corresponde". Un cliente
que limpie la sesión ante un `401` debe ignorar los `403` y puede mostrar un
mensaje de permisos.

Para obtener las tres identidades de prueba (Cliente, Mecánico y
Administrador) existe `scripts/seed_usuarios_prueba.py`; el registro público solo
puede crear clientes, porque los roles se asignan en el servidor.

## Vehículos (MS2)

Todas requieren `Authorization: Bearer <token>` con rol Cliente y un perfil
`Cliente` local en MS2. Una cuenta multirol puede usarlas si incluye Cliente;
el propietario siempre se resuelve desde el JWT y nunca se recibe en el body.

### POST `/api/vehiculos`

Registra un vehículo del cliente autenticado.

La patente es obligatoria, no puede quedar vacía y debe ser única. Se eliminan
espacios exteriores como normalización técnica, pero no se prescribe una regex,
un largo funcional ni una combinación de letras y números. `anio` y
`kilometraje` son enteros opcionales sin rangos funcionales adicionales definidos.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | `{"patente": string, "marca": string, "modelo": string, "anio"?: int, "kilometraje"?: int}` |
| Respuesta OK | `201` con `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Cliente · `404` sin perfil Cliente local · `409` patente existente · `422` datos inválidos · `502/500` de infraestructura |

```json
// Request
{ "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla", "anio": 2018, "kilometraje": 45000 }
// Response 201
{ "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla",
  "anio": 2018, "kilometraje": 45000 }
```

### GET `/api/vehiculos`

Administrador lista todos los vehículos del taller; Cliente lista los suyos. Un
usuario con rol Mecánico (aun con perfil Cliente activo, sin rol Cliente) recibe
`403` y usa `/api/vehiculos/asignados`.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` con rol Cliente o Administrador |
| Body | — |
| Respuesta OK | `200` con lista de `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Cliente o Administrador · `404` sin perfil Cliente local (rol Cliente) · `502/500` de infraestructura |

```json
// Response 200
[ { "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla",
    "anio": 2018, "kilometraje": 45000 } ]
```

### GET `/api/vehiculos/asignados`

Lista los vehículos con órdenes de trabajo asignadas al Mecánico autenticado,
sin duplicados (una misma patente con varias órdenes aparece una sola vez).

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` con rol Mecánico |
| Body | — |
| Respuesta OK | `200` con lista de `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Mecánico · `502/500` de infraestructura |

### GET `/api/vehiculos/{vehiculo_id}`

Devuelve un vehículo según el rol: el Cliente solo los propios, el
Administrador cualquiera del taller y el Mecánico solo los asignados a él.
Un vehículo ajeno y uno inexistente producen el mismo `404`.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `404` inexistente o fuera del alcance del rol · `502/500` de infraestructura |

### PATCH `/api/vehiculos/{vehiculo_id}`

Actualiza parcialmente un vehículo propio (enviar al menos un campo). La
patente y el propietario no son modificables después del registro.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | `{"marca"?: string, "modelo"?: string, "anio"?: int, "kilometraje"?: int}` |
| Respuesta OK | `200` con `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Cliente · `404` vehículo inexistente, ajeno o perfil local ausente · `422` datos inválidos · `502/500` de infraestructura |

```json
// Request
{ "modelo": "Corolla Cross" }
// Response 200
{ "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla Cross",
  "anio": 2018, "kilometraje": 45000 }
```

## Órdenes de trabajo (MS2)

Todos los endpoints requieren `Authorization: Bearer <token>`. La respuesta
`OrdenRespuesta` expone el estado actual y el responsable actual; los
historiales se consultan por separado con `GET /api/ordenes/{orden_id}/historial`:

```json
{
  "orden_id": 31,
  "vehiculo_id": 12,
  "ingreso_id": 18,
  "estado_codigo": 1,
  "mecanico_actual_id": null,
  "creado_por_id": 99,
  "creado_en": "2026-09-28T10:30:00-03:00",
  "actualizado_en": "2026-09-28T10:30:00-03:00"
}
```

### POST `/api/ordenes`

Crea una orden para un vehículo registrado. Solo una identidad con rol
Administrador puede ejecutar la operación; el Cliente no crea directamente su
orden. El servidor controla `ingreso_id`, estado, responsable, creador, fechas e
historiales, por lo que esos campos no se aceptan en el body.

La orden se crea en `Recibido` (`estado_codigo=1`) y puede permanecer con
`mecanico_actual_id=null`. En la misma transacción se crea o reutiliza el ingreso
físico y se registra el historial inicial con el Administrador como actor.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` con rol Administrador |
| Body | `{"vehiculo_id": int positivo}` |
| Respuesta OK | `201` con `OrdenRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Administrador · `404` vehículo inexistente · `422` body inválido o campos controlados · `500` persistencia · `502` MS2 no disponible |

```json
// Request
{ "vehiculo_id": 12 }
```

### GET `/api/ordenes`

Lista solamente las órdenes visibles para la identidad autenticada:

- Administrador: todas las órdenes;
- Cliente: órdenes de vehículos cuyo perfil Cliente le pertenece;
- Mecánico: órdenes cuyo responsable actual coincide con su usuario;
- multirol Cliente + Mecánico: unión de ambos alcances, sin duplicados;
- multirol con Administrador: visibilidad global.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con lista de `OrdenRespuesta` |
| Errores | `401` JWT ausente/inválido · `500` consulta · `502` MS2 no disponible |

### GET `/api/ordenes/{orden_id}`

Devuelve una orden solo si es visible conforme a las mismas reglas del listado.
Una orden ajena y una inexistente se responden de manera indistinguible.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con `OrdenRespuesta` |
| Errores | `401` JWT ausente/inválido · `404` orden inexistente o no visible · `500` consulta · `502` MS2 no disponible |

### PUT `/api/ordenes/{orden_id}/mecanico`

Asigna o reasigna el responsable actual. Solo un Administrador puede ejecutar
la operación y un usuario que además tiene rol Mecánico no puede asignarse a sí
mismo.

En la primera asignación de una orden `Recibido`, MS2 actualiza la orden a
`Esperando diagnóstico` (`estado_codigo=2`) y registra `HistorialAsignacion` e
`HistorialEstado` en la misma transacción. Una reasignación posterior conserva
el estado y registra únicamente el cambio de responsable. Repetir el mismo
`mecanico_id` es idempotente. `Entregado` y `Cancelado` rechazan asignaciones y
reasignaciones.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` con rol Administrador |
| Body | `{"mecanico_id": int positivo, "observacion"?: string no vacío}` |
| Respuesta OK | `200` con `OrdenRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Administrador · `404` orden inexistente · `409` autoasignación o estado terminal · `422` body inválido · `500` persistencia · `502` MS2 no disponible |

```json
// Request
{ "mecanico_id": 50, "observacion": "Asignación inicial" }
// Response 200 en primera asignación
{
  "orden_id": 31,
  "vehiculo_id": 12,
  "ingreso_id": 18,
  "estado_codigo": 2,
  "mecanico_actual_id": 50,
  "creado_por_id": 99,
  "creado_en": "2026-09-28T10:30:00-03:00",
  "actualizado_en": "2026-09-28T10:35:00-03:00"
}
```

`mecanico_id` es hoy una referencia lógica a MS1. La validación remota de
existencia, actividad y rol Mecánico, junto con los límites de capacidad por
mecánico, permanece pendiente de contratos e implementación posteriores.

### GET `/api/ordenes/{orden_id}/historial`

Devuelve los cambios de estado de una orden en orden cronológico, con el actor
que los registró y su observación. Aplica la misma visibilidad del detalle: una
orden ajena y una inexistente responden el mismo `404`.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con lista de `HistorialEstadoRespuesta` |
| Errores | `401` JWT ausente/inválido · `404` orden inexistente o no visible · `500` consulta · `502` MS2 no disponible |

```json
// Response 200
[
  { "historial_id": 40, "orden_id": 31, "estado_anterior": null, "estado_nuevo": 1,
    "actor_usuario_id": 99, "origen": "usuario", "fecha_hora": "2026-09-28T10:30:00-03:00",
    "observacion": null },
  { "historial_id": 41, "orden_id": 31, "estado_anterior": 1, "estado_nuevo": 2,
    "actor_usuario_id": 50, "origen": "usuario", "fecha_hora": "2026-09-28T11:00:00-03:00",
    "observacion": "Inicia evaluación técnica" }
]
```

### PATCH `/api/ordenes/{orden_id}/estado`

Cambia el estado de una orden validando rol, catálogo oficial (1 a 8) y la
transición declarada por el dominio. El Administrador siempre puede ejecutarlo;
el Mecánico solo sobre las órdenes que tiene asignadas. `Entregado` y
`Cancelado` son terminales y rechazan cualquier cambio. El estado y el historial
se actualizan en la misma transacción.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` con rol Administrador o mecánico asignado |
| Body | `{"estado_destino": int positivo, "observacion"?: string no vacío}` |
| Respuesta OK | `200` con `OrdenRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Administrador ni orden asignada · `404` orden inexistente · `409` transición no permitida o terminal · `422` estado de destino desconocido o body inválido · `500` persistencia · `502` MS2 no disponible |

```json
// Request
{ "estado_destino": 2, "observacion": "Inicia evaluación técnica" }
// Response 200
{ "orden_id": 31, "vehiculo_id": 12, "ingreso_id": 18, "estado_codigo": 2,
  "mecanico_actual_id": 50, "creado_por_id": 99,
  "creado_en": "2026-09-28T10:30:00-03:00", "actualizado_en": "2026-09-28T11:00:00-03:00" }
```

## Evidencias multimedia (MS4)

Fotos y videos asociados a una orden de trabajo (diagnóstico, presupuesto,
reparación y entrega). El archivo vive en el almacenamiento de objetos
(MinIO/S3, bucket privado) y sus datos en la base de MS4. Todos los endpoints
requieren `Authorization: Bearer <token>`; MS4 valida el JWT y, antes de leer
o guardar nada, pregunta a MS2 si la orden es visible para ese usuario
reenviando el **mismo** token.

```json
// EvidenciaRespuesta
{
  "evidencia_id": "3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f",
  "orden_id": 31,
  "presupuesto_id": null,
  "contexto": "diagnostico",
  "tipo_archivo": "foto",
  "visible_cliente": false,
  "estado": "confirmada",
  "nombre_original": "frenos delanteros.jpg",
  "content_type": "image/jpeg",
  "tamano_bytes": 482133,
  "creada_en": "2026-10-07T10:15:00-03:00"
}
```

La respuesta **nunca** incluye la clave del objeto en el almacenamiento, el
SHA-256 ni el autor: son datos internos. Para mostrar o bajar el archivo se pide
una URL de descarga (ver más abajo).

Quién ve qué (resumen de `matriz-autorizacion-roles.md` §4.5):

| Rol | Subir | Consultar y descargar |
|---|---|---|
| Cliente | ❌ `403` | Solo de sus órdenes y solo las `visible_cliente=true`, confirmadas y no eliminadas |
| Mecánico | ✅ solo en órdenes que atiende | Todas las no eliminadas de las órdenes que atiende |
| Administrador | ✅ | Todas, incluidas las eliminadas (auditoría) |
| Multirol | Por unión: rige el alcance más amplio | Ídem |

Visibilidad por defecto según `contexto` (si no se envía `visible_cliente`):
`diagnostico` y `reparacion` ocultas; `presupuesto` y `resultado_final`
visibles. En `presupuesto` es obligatorio `presupuesto_id` y la evidencia
siempre es visible.

### POST `/api/evidencias`

Sube una foto o video de una orden. Es `multipart/form-data`, **no** JSON.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` con rol Mecánico (orden asignada) o Administrador |
| Body (multipart) | `archivo` (binario, `image/*` o `video/*`) · `orden_id` (int > 0) · `contexto` (`diagnostico` \| `presupuesto` \| `reparacion` \| `resultado_final`) · `presupuesto_id`? (solo con `presupuesto`) · `visible_cliente`? (`true`/`false`) |
| Cabeceras opcionales | `X-Request-ID` (queda guardado con la evidencia para rastrearla) |
| Respuesta OK | `201` con `EvidenciaRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` rol Cliente (se rechaza antes de procesar el archivo) · `404` `"Orden no encontrada"` (inexistente o no visible) · `413` body > 12 MiB (Gateway) · `422` `"Tipo de archivo no permitido"`, `"El archivo no puede estar vacío"` o formulario inválido · `503` `"El almacenamiento de evidencias no está disponible"` o `"El servicio de órdenes no está disponible"` |

El servidor decide el nombre y la extensión del objeto a partir del
`Content-Type` de la parte `archivo`; el nombre original solo se guarda para
mostrarlo, sin rutas. Si la base falla después de subir, el archivo se borra
(no quedan archivos huérfanos).

```bash
curl -X POST "$GATEWAY/api/evidencias" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-ID: subida-orden-31" \
  -F "archivo=@frenos.jpg;type=image/jpeg" \
  -F "orden_id=31" \
  -F "contexto=diagnostico"
```

```js
// Frontend (fetch): NO fijar Content-Type a mano; el navegador agrega el boundary.
const form = new FormData();
form.append("archivo", archivoSeleccionado);        // File de un <input type="file">
form.append("orden_id", String(ordenId));
form.append("contexto", "resultado_final");
const resp = await fetch(`${API}/api/evidencias`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },
  body: form,
});
if (resp.status === 201) {
  const evidencia = await resp.json();               // EvidenciaRespuesta
}
```

### GET `/api/evidencias?orden_id={orden_id}`

Lista las evidencias de una orden, en orden de creación, filtradas por rol.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Query | `orden_id` (obligatorio, int > 0) |
| Respuesta OK | `200` con lista de `EvidenciaRespuesta` (puede ser `[]`) |
| Errores | `401` JWT ausente/inválido · `404` `"Orden no encontrada"` · `422` falta `orden_id` o no es positivo · `503` MS2 no disponible |

```bash
curl "$GATEWAY/api/evidencias?orden_id=31" -H "Authorization: Bearer $TOKEN"
```

### GET `/api/evidencias/{evidencia_id}`

Devuelve una evidencia con la misma visibilidad del listado. Inexistente,
eliminada (para quien no es Administrador) o fuera de alcance responden el
**mismo** `404`, sin revelar si existe.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Path | `evidencia_id` (UUID) |
| Respuesta OK | `200` con `EvidenciaRespuesta` |
| Errores | `401` JWT ausente/inválido · `404` `"Evidencia no encontrada"` · `422` el id no es UUID · `503` MS2 no disponible |

### GET `/api/evidencias/{evidencia_id}/descarga`

Entrega una **URL prefirmada** del almacenamiento para descargar el archivo.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Path | `evidencia_id` (UUID) |
| Respuesta OK | `200` con `{"url": string, "expira_en": int}` y cabeceras `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` |
| Errores | `401` · `404` `"Evidencia no encontrada"` · `422` · `503` (igual que el detalle) |

```json
// Response 200
{
  "url": "https://almacenamiento.taller.example/evidencias/ordenes/31/3f2b8c1e5d4a4e6b9c7d1a2b3c4d5e6f.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=300&X-Amz-Signature=...",
  "expira_en": 300
}
```

Cómo usarla:

- La URL apunta al almacenamiento, **no** a la Gateway: se abre tal cual, sin
  `Authorization` (la firma ya autoriza esa única descarga).
- Vence en `expira_en` segundos (5 minutos por defecto, configurable con
  `MS4_URL_DESCARGA_TTL_SECONDS`). Vencida, alterada o con otro nombre de
  archivo responde `403` del almacenamiento: se pide una nueva a este endpoint.
- No se guarda en la base ni en `localStorage`, ni se cachea: se pide cada vez
  que el usuario va a ver o bajar el archivo.
- El almacenamiento responde con el `Content-Type` validado y
  `Content-Disposition: attachment; filename="..."` (con `filename*` UTF-8 para
  tildes y ñ), así que el navegador lo descarga en vez de interpretarlo.

```js
// Frontend: botón "Descargar"
const r = await fetch(`${API}/api/evidencias/${id}/descarga`, {
  headers: { Authorization: `Bearer ${token}` },
});
if (r.ok) {
  const { url } = await r.json();
  window.location.assign(url);   // o <a href={url}> recién obtenida
}
```

Para mostrar una miniatura en un `<img>`, también se usa esta URL recién
pedida; si la imagen falla con `403` por vencimiento, se vuelve a pedir.

### Flujo completo (ejemplo)

1. El mecánico inicia sesión (`POST /api/auth/login`) y ve sus órdenes
   (`GET /api/ordenes`).
2. Sube una foto de diagnóstico: `POST /api/evidencias` con
   `contexto=diagnostico` → queda oculta para el cliente.
3. Al entregar, sube la foto final con `contexto=resultado_final` → visible.
4. El cliente lista `GET /api/evidencias?orden_id=31` y solo ve la foto final.
5. Para verla pide `GET /api/evidencias/{id}/descarga` y abre la `url`.

Configuración en el despliegue: `MS4_S3_PUBLIC_ENDPOINT` debe ser la URL
pública HTTPS del almacenamiento (la que verá el navegador); la firma incluye
el host, así que una URL firmada con el nombre interno de la red Docker no
funciona fuera de ella. Detalle en `estudio-urls-firmadas.md`.

Videos: por ahora entran por este mismo endpoint dentro del límite de 12 MiB.
La subida directa de videos grandes al almacenamiento (flujo C, POST
prefirmado) está planificada para una semana posterior.

Pruebas que respaldan este contrato: `tests/test_ms4_api_evidencias.py`,
`tests/test_ms4_autorizacion_evidencias.py`, `tests/test_ms4_ciclo_archivos.py`,
`tests/test_gateway_evidencias.py` y `tests/test_gateway_openapi_evidencias.py`
(los ejemplos del Swagger se comparan con las respuestas reales de MS4).

## Contratos todavía no publicados

Las siguientes capacidades no tienen un endpoint implementado y no deben ser
consumidas como parte del contrato actual:

| Capacidad | Situación actual |
|---|---|
| Capacidad y máximo de órdenes activas | Subsistema de una semana posterior |
| Presupuestos, repuestos e inventario | Los contratos de MS3 se publicarán cuando sus endpoints estén definidos y verificados |

El frontend web y la aplicación móvil deben consumir exclusivamente las rutas
publicadas por la API Gateway con prefijo `/api`. La existencia de una llamada o
una interfaz provisional en un cliente no convierte una ruta futura en contrato
implementado.
