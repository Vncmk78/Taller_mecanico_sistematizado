# Auditoría de contratos OpenAPI consumidos por el frontend

Levantamiento de TODAS las llamadas HTTP que hace la aplicación web `frontend/`
(React + Vite + TypeScript) contra la API Gateway, verificado contra las
fuentes de verdad del backend:

- `backend/docs/contratos-api-gateway.md`
- Swagger del API Gateway (`backend/gateway/openapi.py`)
- Rutas reales de `backend/services/ms1_auth` y `backend/services/ms2_taller`

Todas las llamadas salen de la capa de infraestructura `src/infrastructure/api/`
a través del cliente `src/infrastructure/config/apiClient.ts`, con base
`VITE_API_URL || '/api'` y cabecera `Authorization: Bearer <jwt>`.

Fecha de verificación: 30 sep 2026 (Sprint 2, Semana 4), tercera revisión tras
retirar los datos simulados y después de que el backend actualizara sus
contratos con ejemplos y respuestas comunes. Verificado contra la implementación
real de `backend/services/ms1_auth` y `backend/services/ms2_taller`, y contra
`backend/gateway/contratos/`. Las diferencias encontradas están en "Registro de
discrepancias entre el frontend y el contrato de la API".

## Inventario de endpoints consumidos

| Servicio / método | HTTP | Ruta completa | Páginas | Alcance en MS2 | Resultado |
| --- | --- | --- | --- | --- | --- |
| `AuthService.login` | POST | `/api/auth/login` | `/login` | MS1: público | OK |
| `AuthService.getProfile` | GET | `/api/auth/me` | restauración de sesión | MS1: autenticado | OK |
| `VehicleService.getMyVehicles` | GET | `/api/vehiculos` | `/client/vehiculos` | Cliente (propios) o Administrador (todos) | OK |
| `VehicleService.getAllVehicles` | GET | `/api/vehiculos` | `/admin/vehiculos` | Administrador | OK |
| `VehicleService.getAssignedVehicles` | GET | `/api/vehiculos/asignados` | `/mechanic/vehiculos` | Mecánico (asignados) | OK |
| `VehicleService.getVehicleById` | GET | `/api/vehiculos/{id}` | detalle vehículo (cliente, admin, mecánico) | Administrador (cualquiera), Cliente (propio), Mecánico (asignado) | OK (404 fuera de alcance) |
| `VehicleService.createVehicle` | POST | `/api/vehiculos` | `/client/vehiculos/nuevo` | Cliente | OK |
| `OrderService.getOrders` | GET | `/api/ordenes` | órdenes (admin, cliente, mecánico) | Filtra por rol | OK |
| `OrderService.getOrderById` | GET | `/api/ordenes/{id}` | detalle de orden | Alcance por rol | OK |
| `OrderService.getOrderHistory` | GET | `/api/ordenes/{id}/historial` | historial en detalle de orden | Alcance por rol | OK |
| `OrderService.cambiarEstado` | PATCH | `/api/ordenes/{id}/estado` | `MechanicStatusPage` | Administrador o mecánico asignado | OK |

El alcance por rol lo aplica el microservicio, no el frontend: el navegador
recibe únicamente las filas que corresponden al usuario autenticado. Por eso las
vistas ya no aplican filtros de identidad en modo offline (la caché conserva la
misma respuesta que devolvió la Gateway).

## Campos que la Gateway expone y el frontend no puede nombrar

MS2 no resuelve datos de MS1, así que el contrato entrega identificadores y no
nombres. La interfaz muestra el identificador real en lugar de datos simulados:

| Dato | Qué entrega el contrato | Qué muestra la interfaz |
| --- | --- | --- |
| Propietario del vehículo | `VehiculoRespuesta.cliente_id` (perfil Cliente de MS2) | `Cliente #<cliente_id>` |
| Mecánico de la orden | `OrdenRespuesta.mecanico_actual_id` | `Mecánico <id>`, o `Sin asignar` |
| Actor del cambio de estado | `HistorialEstado.actor_usuario_id` | Identificador numérico |
| Patente del vehículo en la orden | No viene en `OrdenRespuesta` | Se resuelve desde la caché de vehículos del portal |

`cliente_id` (MS2) y `usuario_id` (MS1, el de la sesión) son espacios de
identificadores distintos. El portal Cliente sigue usando el `id` de la sesión
para resolver la pertenencia de cada ficha en la caché compartida entre
portales (`getMyVehicles(clientId)` y `getVehicleById(id, clientId)`), mientras
que Administrador y Mecánico muestran el `cliente_id` real que llega en la
respuesta.

## Endpoints que el microservicio expone y el frontend aún no usa

Referencia para coordinación (no asumir; se habilitan cuando las vistas lo
requieran):

| Ruta | MS | Observación |
| --- | --- | --- |
| `POST /api/ordenes` | MS2 | Creación de orden (rol Administrador). Sin vista aún. |
| `PUT /api/ordenes/{id}/mecanico` | MS2 | Asignación/reasignación de mecánico (Admin). Sin vista aún. |
| `PATCH /api/vehiculos/{id}` | MS2 | Edición de vehículo. Sin vista aún. |
| `POST /api/auth/register` | MS1 | Registro de usuario. Sin vista aún. |

## Estados de carga, vacío y error

El frontend clasifica cada fallo antes de decidir qué muestra, para no rotular
como "sin conexión" un error que el servidor sí respondió. La clasificación vive
en `isOfflineError` (`src/infrastructure/api/errors.ts`):

| Situación | `isOffline` | Qué ve el usuario |
| --- | --- | --- |
| Sin respuesta HTTP (DNS, red caída, Axios sin `response`) | `true` | Banner "No se pudo conectar con el servidor" + caché |
| HTTP `502` / `503` / `504` (Gateway o microservicio caído) | `true` | Banner de servicio caído + caché, con el mensaje del backend |
| HTTP `500` y otros `5xx` con respuesta | `false` | "El servidor tuvo un problema. Intente más tarde." + botón Reintentar |
| HTTP `401` / `403` | `false` | Error; la sesión se restaura por separado en `AuthService` |
| HTTP `404` en un detalle | `false` | Estado vacío "no encontrado" (el recurso existe, pero no está en el alcance del rol) |
| HTTP `404` en un listado | `false` | Estado vacío de la colección |
| HTTP `409` / `422` | `false` | Mensaje de negocio de MS2, sin tratarlo como caída de conexión |
| Colección vacía con `200` | `false` | Estado vacío del portal, con su acción correspondiente |

Cuando la respuesta trae `request_id`, el estado de error o el banner agregan una
línea `Referencia: <id>` para que el usuario pueda entregar la referencia al
soporte y el fallo se rastree en los logs del backend.

Reglas que se aplican en listados, detalles e historial:

- `fetchCollection` reinicia `status`/`error`/`isOffline` al empezar cada
  intento, así que un reintento limpio no arrastra el error anterior.
- Un fallo conserva la caché: se avisa y se siguen mostrando los últimos datos
  conocidos. Solo sin copia local el listado o el detalle cae al estado de error.
- En un detalle, `404` produce `notFound` y cualquier otro fallo sin caché produce
  `failed`; son estados distintos y las vistas los tratan distinto para no
  mostrar un "no encontrado" que no es cierto.
- En el historial de la orden, un fallo muestra "No fue posible mostrar el
  historial de estados de esta orden." en lugar del vacío "Aún no hay registros".

Componentes compartidos por los tres portales: `EmptyState` (vacío),
`ErrorState` (error reintentable), `RetryButton` y `OfflineBanner`.

## Errores reales del backend

La Gateway responde con su propio formato (`gateway/esquemas.py`): `detail` es un
string legible y `error` trae `codigo`, `estado`, `ruta` y `request_id`. Los errores
que emite un microservicio pasan tal cual por el proxy y llegan solo con `detail`.

| Origen | Cuerpo | Cómo lo muestra el frontend |
| --- | --- | --- |
| `404` | `{ detail: "Ruta no encontrada", error: { codigo: "RUTA_NO_ENCONTRADA", ... } }` | Estado vacío del recurso |
| `405` | `{ detail: "Método no permitido", error: { codigo: "METODO_NO_PERMITIDO", ... } }` | Mensaje del backend |
| `500` | `{ detail: "Ocurrió un error inesperado en la Gateway.", error: { codigo: "ERROR_INTERNO", ... } }` | Error reintentable + referencia |
| `500` | `{ detail: "El servicio respondió con un error inesperado.", error: { codigo: "ERROR_MICROSERVICIO", ... } }` | Error reintentable + referencia |
| `502` | `{ detail: "El servicio no está disponible. Intente más tarde.", ... }` | Banner de servicio caído + caché |
| `503` | `{ detail: "La Gateway está ocupada. Intente más tarde.", ... }` | Banner de servicio caído + caché |
| `504` | `{ detail: "El servicio tardó demasiado en responder. Intente más tarde.", ... }` | Banner de servicio caído + caché |
| `409` (MS2) | `{ detail: "La patente ya está registrada" }` | Error en el campo Patente del formulario |
| `409` (MS1) | `{ detail: "El correo ya está registrado" }` | Mensaje de negocio |
| `401` (MS1) | `{ detail: "Correo o contraseña incorrectos" }` / `{ detail: "Token inválido o expirado" }` | Mensaje de negocio |
| `403` (MS1) | `{ detail: "No tienes permiso para realizar esta operación" }` | Mensaje de negocio |
| `422` | `detail` como lista `{ loc, msg, type }` o como string (`"Estado de destino desconocido: 999"`, `"La contraseña no puede superar 72 bytes"`) | Primer `msg` de la lista, o el string |
| `500` (MS2) | `{ detail: "No fue posible consultar los vehículos" }` | Error reintentable |

`getApiErrorMessage` siempre prefiere el `detail` real sobre cualquier mensaje
genérico por status, incluidos los `502/503/504`: aunque se marquen como fallo de
transporte, el texto que ve el usuario es el que escribió el backend.
`getApiErrorRequestId` extrae el `request_id` (con respaldo en la cabecera
`X-Request-ID`) y `getApiErrorCode` el código del catálogo, para clasificar sin
parsear el mensaje. Cuando el error no trae ninguno de los dos, la interfaz no
muestra ninguna referencia en vez de inventar una.

Los cuerpos literales están en `src/infrastructure/mocks/payloads.reales.ts`, con
la referencia al archivo del backend del que salió cada uno, y se prueban contra
`errors.test.ts`.

## Datos opcionales y decisiones de mapeo

- `VehiculoRespuesta.anio` y `kilometraje` son opcionales en el contrato: un
  vehículo registrado puede venir sin ellos. `VehicleService` los normaliza a `0`
  y `vehicleDisplay.ts` traduce ese `0` a "Sin especificar", para no mostrar
  "Año: 0". Limitación asumida: un vehículo con 0 km reales queda indistinguible
  de uno sin dato. El formulario de registro también los trata como opcionales
  y los manda en `null` explícito, que es el valor que el contrato declara.
- `OrdenRespuesta.mecanico_actual_id` y los campos del historial
  (`estado_anterior`, `actor_usuario_id`, `observacion`) pueden llegar en `null` y
  el mapeo los conserva como `null`/`undefined`, sin inventar valores.
- `UsuarioRespuesta.roles` es una lista. El dominio tiene un único `role` y hoy
  gana el primero (`roles[0]`), que es el que define el portal de ingreso. Queda
  fijado con una prueba en `AuthService.test.ts`; si el backend llegara a entregar
  dos roles con reglas de portal distintas, habría que revisarlo.
- Las fechas llegan con offset `-03:00`. El mapeo las conserva tal cual y
  `orderDisplay.ts` las formatea con `es-CL`; Vitest corre con
  `TZ: America/Santiago` para que el texto esperado sea estable.

## Registro de discrepancias entre el frontend y el contrato de la API

Auditoría punto por punto de lo que el frontend exige, consume o asume contra lo
que la Gateway y los microservicios declaran y responden. Cada fila está cerrada
con la evidencia del archivo del backend que la demuestra.

| # | Dónde | Qué exigía o asumía el frontend | Qué declara el contrato | Impacto | Estado |
|---|---|---|---|---|---|
| D1 | `ClientVehicleFormPage.tsx` | `patent` con patrón `/^[A-Za-z]{4}-\d{2}$/` | `patente: str` con `min_length=1` y **sin** `pattern` (`gateway/contratos/vehiculos.py`, `ms2_taller/schemas/vehiculo.py`; el test de MS2 afirma `assert "pattern" not in patente`) | La UI rechazaba el propio ejemplo del contrato (`AB1234`) | **Resuelta** |
| D2 | `ClientVehicleFormPage.tsx` | `marca`/`modelo` sin longitud máxima | `marca`/`modelo` con `min_length=1, max_length=60` | La UI aceptaba texto de más de 60 caracteres y el backend respondía `422` | **Resuelta** |
| D3 | `ClientVehicleFormPage.tsx` | `anio` y `kilometraje` obligatorios, con rangos inventados (año 1980–actual+1, km 0–999999) | `anio`/`kilometraje` son `int \| None = None` y **no declaran cotas** | No se podía registrar un vehículo sin año ni km, y datos válidos (año 1995, 1.500.000 km) quedaban fuera de la UI | **Resuelta** |
| D4 | Este documento | Que `backend/docs/contratos-api-gateway.md` estaba desactualizado | Ese documento ya registra `/api/vehiculos/asignados`, `/api/ordenes/{id}/historial`, `PATCH /api/ordenes/{id}/estado` y el `cliente_id` de la respuesta de vehículo | El registro del frontend afirmaba una deuda que ya no existía | **Resuelta** |

Cómo se cerró cada una:

- **D1**: el formulario ahora valida `patent` con `min(1)` y su `placeholder` pasó
  de `ABCD-12` a `AB1234`. Se sigue normalizando a mayúsculas al enviar. Fijado en
  `ClientVehicleFormPage.test.tsx`.
- **D2**: `marca` y `modelo` ahora tienen `.max(60)`, igual que el backend. El
  `422` real que recibía el usuario por texto largo quedó como fixture
  (`textoVehiculoDemasiadoLargo` en `payloads.reales.ts`) y como prueba en
  `errors.test.ts`.
- **D3**: `anio` y `kilometraje` son opcionales en el formulario (etiquetados
  "(opcional)") y viajan como `null` explícito, que es lo que acepta el
  contrato; `CreateVehicleInput` los tipa `number | null`. Se conserva el
  rechazo de un valor no numérico o negativo, que sí es un dato inválido, pero
  se eliminaron los topes que el contrato nunca declaró.
- **D4**: la sección "Desactualizaciones del documento de contrato" se reemplazó
  por el estado real verificado del documento del backend.

### Controles verificados sin discrepancia

Se revisaron también los puntos donde el frontend depende del contrato y **no**
hay diferencias:

- **Errores de la Gateway**: `ErrorRespuesta` conserva `detail` como string de
  primer nivel precisamente para que el frontend lo muestre
  (`gateway/esquemas.py`), acompañado de `error.{codigo, estado, ruta,
  request_id}`. Es lo que leen `getApiErrorMessage`, `getApiErrorRequestId` y
  `getApiErrorCode`.
- **Endpoints**: los tres que el frontend consume y el contrato había dejado
  fuera de la documentación existen y responden lo que el mapeo espera
  (`/vehiculos/asignados`, `/ordenes/{id}/historial`, `/ordenes/{id}/estado`).
- **`PATCH /api/ordenes/{id}/estado`**: devuelve la `OrdenRespuesta` completa,
  que es lo que el frontend da por hecho al mapear la respuesta.
- **Cuerpo del cambio de estado**: `{ estado_destino, observacion }` coincide con
  `CambioEstadoSolicitud`. La observación vacía se omite en vez de enviarse como
  `""`, que violaría su `min_length=1`.
- **`extra="forbid"`** en los cuerpos de creación: el frontend envía
  exactamente los campos declarados y nunca `cliente_id` (el propietario lo
  resuelve la Gateway desde el JWT).

### Pendiente de decisión (backend, no se modificó)

Estas no se tocan desde el frontend porque son del contrato y del dominio:

1. **El contrato no acota `anio` ni `kilometraje`.** Acepta cualquier entero,
   así que admite valores sin sentido (año 0, kilometraje negativo). La regla
   correcta sería declarar `ge`/`le` en `gateway/contratos/vehiculos.py`;
   mientras tanto el formulario los manda sin rango, alineado con lo que el
   servidor acepta.
2. **`origen` del historial es `str` y no un conjunto cerrado** en el contrato,
   aunque el dominio solo admite `usuario` o `sistema` y el frontend castea a esa
   unión sin validar. Cerrarlo en el contrato evitaría que un valor nuevo llegue
   a la interfaz sin avisar.
3. **`origen: 'sistema' → actor_usuario_id` en `null`** es una coherencia que hoy
   solo garantiza la base (`ms2_taller/models/historial_estado.py`). El frontend
   conserva los tres campos tal cual llegan, sin inventar valores.

## Decisiones de la revisión (alcance frontend)

- No se inventan endpoints: los servicios conservan las rutas del contrato y se
  fijan con pruebas de contrato en `OrderService.test.ts` y
  `VehicleService.test.ts`.
- Ninguna vista depende de datos simulados: los stores arrancan vacíos y solo
  se llenan con respuestas de la Gateway. Los archivos de
  `src/infrastructure/mocks/` quedan como fixtures exclusivos de los tests.
- El mapeo y los errores se prueban contra los cuerpos literales que devuelve el
  backend (`src/infrastructure/mocks/payloads.reales.ts`), no contra payloads
  inventados en el test.

## Histórico: desajuste del formato de patente (resuelto)

Este desajuste se detectó al revisar los contratos y **ya no está**: queda
registrado para que no se reintroduzca.

El formulario de registro exigía la patente con `/^[A-Za-z]{4}-\d{2}$/` (por
ejemplo `ABCD-12`), pero el backend solo exige `min_length=1` y su propio test
afirma que el contrato **no** define un patrón
(`backend/tests/test_vehiculos_api.py`: `assert "pattern" not in patente`). El
ejemplo real de la Gateway usa `AB1234`, un formato que el formulario rechazaba,
así que la UI era más restrictiva que el servidor.

Se resolvió alineando el formulario con el contrato: la patente se valida con
`min(1)` y su `placeholder` es ahora `AB1234`. La decisión de producto que
quedaba pendiente —si el negocio exige el formato chileno o se acepta el que
envíe el backend— se resolvió a favor del contrato, que es la autoridad: si en
algún momento se quiere exigir un formato, corresponde declararlo en el backend
y no solo en el formulario. Ver "Registro de discrepancias", fila D1.
