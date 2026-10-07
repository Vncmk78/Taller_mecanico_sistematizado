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
| Administrador | No obtiene acceso global al endpoint de vehículos salvo que la cuenta también tenga rol Cliente y perfil local | Crea órdenes, ve todas y asigna o reasigna mecánicos |
| Cliente | Registra, lista, consulta y modifica únicamente sus vehículos | Lista y consulta únicamente órdenes asociadas a sus vehículos; no crea órdenes |
| Mecánico | No existe todavía un endpoint de vehículos asignados | Lista y consulta únicamente órdenes cuyo `mecanico_actual_id` coincide con su usuario |
| Multirol | Acumula los permisos de sus roles | Une los alcances Cliente y Mecánico sin duplicados; si incluye Administrador, conserva visibilidad global |

Una orden inexistente y una orden fuera del alcance del Cliente o Mecánico
responden el mismo `404`, para no revelar la existencia de recursos ajenos.

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

Lista los vehículos del cliente autenticado.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con lista de `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Cliente · `404` sin perfil Cliente local · `502/500` de infraestructura |

```json
// Response 200
[ { "vehiculo_id": 12, "patente": "AB1234", "marca": "Toyota", "modelo": "Corolla",
    "anio": 2018, "kilometraje": 45000 } ]
```

### GET `/api/vehiculos/{vehiculo_id}`

Consulta un vehículo únicamente cuando pertenece al Cliente autenticado. Un
vehículo ajeno y uno inexistente producen el mismo `404`.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con `VehiculoRespuesta` |
| Errores | `401` JWT ausente/inválido · `403` sin rol Cliente · `404` vehículo inexistente, ajeno o perfil local ausente · `502/500` de infraestructura |

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
`OrdenRespuesta` expone el estado actual y el responsable actual, pero no
incluye los historiales completos; el historial de estados se consulta mediante
su endpoint específico:

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

### GET `/api/ordenes/{orden_id}/historial`

Devuelve el historial completo de estados de una orden visible. Reutiliza la
visibilidad del detalle: Administrador ve todas las órdenes, Cliente las de sus
vehículos y Mecánico las actualmente asignadas; multirol combina los alcances.
Una orden ajena y una inexistente devuelven el mismo `404`.

Los registros se ordenan por `fecha_hora ASC` y, si coinciden las fechas, por
`historial_id ASC`. Incluye el registro inicial (`estado_anterior=null`). Una
orden visible sin registros devuelve `[]`; la consulta no crea ni modifica datos.

| Atributo | Descripción |
|---|---|
| Auth | `Authorization: Bearer <token>` |
| Body | — |
| Respuesta OK | `200` con lista de `HistorialEstadoRespuesta` |
| Errores | `401` JWT ausente/inválido · `404` orden inexistente o no visible · `422` identificador inválido · `500` consulta · `502` MS2 no disponible |

Cada registro contiene `historial_id`, `orden_id`, `estado_anterior` (código o
`null`), `estado_nuevo` (código), `actor_usuario_id` (referencia lógica a MS1 o
`null` para origen `sistema`), `fecha_hora`, `origen` (`usuario` o `sistema`) y
`observacion` (texto o `null`). El actor identifica quién originó el cambio,
no necesariamente al mecánico asignado. No se consultan nombres en MS1.

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

## Contratos todavía no publicados

Las siguientes capacidades no tienen un endpoint implementado y no deben ser
consumidas como parte del contrato de Semana 3:

| Capacidad | Situación actual |
|---|---|
| Cambio general de estado | No existe un endpoint; solo la primera asignación realiza la transición implementada |
| Vehículos asignados a un mecánico | No existe `/api/vehiculos/asignados` |
| Capacidad y máximo de órdenes activas | Subsistema de una semana posterior |
| Presupuestos, repuestos e inventario | Los contratos de MS3 se publicarán cuando sus endpoints estén definidos y verificados |
| Evidencias multimedia | Los contratos de MS4 se publicarán cuando sus endpoints estén definidos y verificados |

El frontend web y la aplicación móvil deben consumir exclusivamente las rutas
publicadas por la API Gateway con prefijo `/api`. La existencia de una llamada o
una interfaz provisional en un cliente no convierte una ruta futura en contrato
implementado.
