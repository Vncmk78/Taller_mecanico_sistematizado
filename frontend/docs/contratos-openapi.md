# Auditoría de contratos OpenAPI consumidos por el frontend

Levantamiento de TODAS las llamadas HTTP que hace la aplicación web `frontend/`
(React + Vite + TypeScript) contra la API Gateway, verificado contra las
fuentes de verdad del backend:

- `backend/docs/contratos-api-gateway.md`
- Swagger del API Gateway (`backend/gateway/openapi.py`)

Todas las llamadas salen de la capa de infraestructura `src/infrastructure/api/`
a través del cliente `src/infrastructure/config/apiClient.ts`, con base
`VITE_API_URL || '/api'` y cabecera `Authorization: Bearer <jwt>`.

Fecha de verificación: 30 sep 2026 (Sprint 2, Semana 4).
Verificado contra la implementación real de `backend/services/ms1_auth` y
`backend/services/ms2_taller`.

## Inventario de endpoints consumidos

| Servicio / método | HTTP | Ruta completa | Páginas | Contrato doc | MS real | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| `AuthService.login` | POST | `/api/auth/login` | `/login` | Documentado | MS1: existe | OK, coincide |
| `AuthService.getProfile` | GET | `/api/auth/me` | restauración de sesión | Documentado | MS1: existe | OK, coincide |
| `VehicleService.getMyVehicles` | GET | `/api/vehiculos` | `/client/vehiculos` | Documentado (rol Cliente) | MS2: existe | OK, coincide |
| `VehicleService.getAllVehicles` | GET | `/api/vehiculos` | `/admin/vehiculos` | Documentado (rol Cliente) | MS2: requiere Cliente | Riesgo de rol: el Administrador recibe 403 |
| `VehicleService.getAssignedVehicles` | GET | `/api/vehiculos/asignados` | `/mechanic/vehiculos` | No documentado | MS2: NO existe | Dependencia pendiente del backend (422 hoy) |
| `VehicleService.getVehicleById` | GET | `/api/vehiculos/{id}` | detalle vehículo (cliente, admin, mecánico) | Documentado (rol Cliente) | MS2: requiere Cliente | Riesgo de rol: Admin y Mecánico reciben 403 |
| `VehicleService.createVehicle` | POST | `/api/vehiculos` | `/client/vehiculos/nuevo` | Documentado (body coincide) | MS2: existe | OK, coincide |
| `OrderService.getOrders` | GET | `/api/ordenes` | órdenes (admin, cliente, mecánico) | Marcado "Pendiente" | MS2: existe (filtra por rol) | OK en MS, contrato desactualizado |
| `OrderService.getOrderById` | GET | `/api/ordenes/{id}` | detalle de orden | Marcado "Pendiente" | MS2: existe (alcance por rol) | OK en MS, contrato desactualizado |
| `OrderService.getOrderHistory` | GET | `/api/ordenes/{id}/historial` | historial en detalle de orden | No documentado | MS2: NO existe | Dependencia pendiente del backend (404 hoy) |

## Endpoints que el microservicio expone y el frontend aún no usa

Referencia para coordinación (no asumir; se habilitan cuando las vistas lo
requieran):

| Ruta | MS | Observación |
| --- | --- | --- |
| `POST /api/ordenes` | MS2 | Creación de orden (rol Administrador). Sin vista aún. |
| `PUT /api/ordenes/{id}/mecanico` | MS2 | Asignación/reasignación de mecánico (Admin). Sin vista aún. |
| `PATCH /api/vehiculos/{id}` | MS2 | Edición de vehículo. Sin vista aún. |
| `POST /api/auth/register` | MS1 | Registro de usuario. Sin vista aún. |

## Dependencias pendientes del backend (coordinación)

Tareas de otros integrantes que el frontend necesita antes de retirar los datos
de demostración:

1. **`GET /api/vehiculos/asignados` (MS2)**: endpoint del portal Mecánico.
   Hoy `getAssignedVehicles()` no tiene dónde apuntar y la vista
   `MechanicVehiclesPage` compensa filtrando contra `mockAssignedVehicleIds`
   de `src/infrastructure/mocks/vehicles.mock.ts`.
2. **`GET /api/ordenes/{id}/historial` (MS2)**: historial de estados que consume
   `OrderService.getOrderHistory()` en el detalle de orden. El comentario de
   contrato en `OrderService.ts` ya lo marca como `endpoint futuro`.
3. **Acceso por rol a vehículos (MS2)**: `GET /api/vehiculos` y
   `GET /api/vehiculos/{id}` solo aceptan rol Cliente en la implementación
   actual; las vistas de catálogo (Admin) y asignados/detalle (Mecánico)
   necesitan que el microservicio amplíe el alcance por rol, igual que ya hace
   en `/api/ordenes`.

## Desactualizaciones del documento de contrato

`backend/docs/contratos-api-gateway.md` figura `/api/ordenes` como
"Pendiente (todavía sin endpoints en los microservicios)", pero `ms2_taller`
ya lo implementa (`POST/GET /api/ordenes`, `GET /api/ordenes/{id}` y
`PUT /api/ordenes/{id}/mecanico`). Correspondería al equipo de backend
actualizar el doc y el Swagger de la Gateway.

## Decisiones de la revisión (alcance frontend)

- No se inventan endpoints: los servicios conservan las rutas del contrato y se
  fijan con pruebas de contrato en `OrderService.test.ts` y
  `VehicleService.test.ts`.
- Las vistas que dependen de endpoints inexistentes (mecánico asignados,
  historial de orden) continúan con datos mock sin bloquear el sprint; la
  dependencia queda documentada arriba.