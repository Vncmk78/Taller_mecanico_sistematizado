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

Fecha de verificación: 30 sep 2026 (Sprint 2, Semana 4), segunda revisión tras
retirar los datos simulados. Verificado contra la implementación real de
`backend/services/ms1_auth` y `backend/services/ms2_taller`.

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
| HTTP `502` / `503` / `504` (Gateway o microservicio caído) | `true` | Mismo banner de conexión |
| HTTP `500` y otros `5xx` con respuesta | `false` | "El servidor tuvo un problema. Intente más tarde." + botón Reintentar |
| HTTP `401` / `403` | `false` | Error; la sesión se restaura por separado en `AuthService` |
| HTTP `404` en un detalle | `false` | Estado vacío "no encontrado" (el recurso existe, pero no está en el alcance del rol) |
| HTTP `404` en un listado | `false` | Estado vacío de la colección |
| HTTP `409` / `422` | `false` | Mensaje de negocio de MS2, sin tratarlo como caída de conexión |
| Colección vacía con `200` | `false` | Estado vacío del portal, con su acción correspondiente |

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

## Desactualizaciones del documento de contrato

`backend/docs/contratos-api-gateway.md` sigue figurando `/api/ordenes` como
"Pendiente (todavía sin endpoints en los microservicios)" y no registra
`/api/ordenes/{id}/historial`, `/api/ordenes/{id}/estado`, `/api/vehiculos/asignados`
ni el `cliente_id` de `VehiculoRespuesta`. `ms2_taller` ya los implementa y el
Swagger de la Gateway los documenta. Correspondería al equipo de backend
actualizar ese documento.

## Decisiones de la revisión (alcance frontend)

- No se inventan endpoints: los servicios conservan las rutas del contrato y se
  fijan con pruebas de contrato en `OrderService.test.ts` y
  `VehicleService.test.ts`.
- Ninguna vista depende de datos simulados: los stores arrancan vacíos y solo
  se llenan con respuestas de la Gateway. Los archivos de
  `src/infrastructure/mocks/` quedan como fixtures exclusivos de los tests.
