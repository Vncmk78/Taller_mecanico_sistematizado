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
  `MICROSERVICIO_INALCANZABLE` (502) y `ERROR_INTERNO` (500), todos con el
  cuerpo `{"detail": "...", "error": {"codigo", "estado", "ruta", "request_id"}}`.
- Errores de los microservicios: `{"detail": "mensaje"}` con su status code.
  En los `422` (validación de body en MS1/MS2), `detail` es una **lista** de
  errores de FastAPI, no un string:

  ```json
  { "detail": [ { "loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error" } ] }
  ```

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

## Vehículos (MS2)

Todas requieren `Authorization: Bearer <token>` con rol Cliente.

### POST `/api/vehiculos`

Registra un vehículo del cliente autenticado.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | `{"patente": string, "marca": string, "modelo": string, "anio"?: int, "kilometraje"?: int}` |
| Respuesta OK | `201` con `VehiculoRespuesta` |
| Errores | `401/403` de auth · `409` patente existente · `422` datos inválidos · `404/502/500` de la Gateway |

```json
// Request
{ "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla", "anio": 2018, "kilometraje": 45000 }
// Response 201
{ "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla",
  "anio": 2018, "kilometraje": 45000 }
```

### GET `/api/vehiculos`

Lista los vehículos del cliente autenticado.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con lista de `VehiculoRespuesta` |
| Errores | `401/403` de auth · `404/502/500` de la Gateway |

```json
// Response 200
[ { "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla",
    "anio": 2018, "kilometraje": 45000 } ]
```

### GET `/api/vehiculos/{vehiculo_id}`

Consulta un vehículo del cliente autenticado.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con `VehiculoRespuesta` |
| Errores | `401/403` de auth · `404` vehículo no encontrado (del microservicio) · `502/500` de la Gateway |

### PATCH `/api/vehiculos/{vehiculo_id}`

Actualiza parcialmente un vehículo (enviar al menos un campo).

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | `{"marca"?: string, "modelo"?: string, "anio"?: int, "kilometraje"?: int}` |
| Respuesta OK | `200` con `VehiculoRespuesta` |
| Errores | `401/403` de auth · `404` vehículo no encontrado · `422` datos inválidos · `502/500` de la Gateway |

```json
// Request
{ "modelo": "Corolla Cross" }
// Response 200
{ "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla Cross",
  "anio": 2018, "kilometraje": 45000 }
```

## Pendientes (todavía sin endpoints en los microservicios)

| Área | Ruta prevista |
|---|---|
| Órdenes de trabajo | `/api/ordenes` |
| Presupuestos | `/api/presupuestos` |
| Repuestos / proveedores / inventario | `/api/repuestos`, `/api/proveedores`, `/api/inventario` |
| Evidencias multimedia | `/api/evidencias` |

Su contrato se agregará cuando MS2/MS3/MS4 definan los endpoints; no se
inventan aquí.