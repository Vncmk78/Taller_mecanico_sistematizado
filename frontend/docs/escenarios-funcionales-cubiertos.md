# Escenarios Funcionales Cubiertos

Documento de referencia de los escenarios funcionales cubiertos por el frontend del sistema TallerConect, basado en las pruebas existentes y la implementación actual.

## 1. Autenticación y Navegación por Roles

| Escenario | Descripción | Estado |
|---|---|---|
| **Sin sesión** | Al intentar acceder a rutas protegidas (`/admin`, `/client`, `/mechanic`) se redirige a `/login`. | Cubierto |
| **Ruta inexistente** | Al navegar a una ruta no definida, el sistema redirige al home público. | Cubierto |
| **Login diferenciado** | El sistema permite acceso según el rol autenticado (administrador, cliente o mecánico). | Cubierto |
| **Acceso denegado** | Cuando un usuario intenta acceder a un portal que no le corresponde, se muestra la vista "Acceso Denegado" con opción para volver a su propio panel. | Cubierto |
| **Sesión inválida** | Con token presente pero sin perfil válido, se redirige a `/login` sin mostrar acceso denegado. | Cubierto |
| **Registro público** | El registro crea únicamente cuentas con rol Cliente (`POST /auth/register`). | Cubierto |
| **Perfil de cliente** | El portal Cliente exige el perfil de cliente de MS2 (`ClientProfileGate`) antes de mostrar sus vistas. | Cubierto |

## 2. Panel Administrativo

| Escenario | Descripción | Estado |
|---|---|---|
| **Panel inicial** | Acceso al dashboard con resumen operativo (órdenes totales/activas, vehículos, mecánicos, estados). | Cubierto |
| **Carga de indicadores** | Muestra estado de carga mientras se obtienen los datos. | Cubierto |
| **Manejo de errores** | Muestra `ErrorState` con botón "Reintentar" ante fallos en la carga del resumen. | Cubierto |
| **Carga de mecánicos** | Visualización de mecánicos con sus órdenes totales y activas, ordenados por carga. | Cubierto |
| **Paginación** | Paginación de la carga de mecánicos (5 por página) con navegación y contador. | Cubierto |
| **Navegación del panel** | Acceso a órdenes, nuevas atenciones, cancelaciones, clientes, usuarios y roles, configuración, avisos, vehículos, inventario y distribuidores desde el menú lateral. | Cubierto |
| **Clientes** | Listado y búsqueda de cuentas de cliente. | Cubierto |
| **Nuevas atenciones** | Listado y detalle de las solicitudes de nueva atención. | Cubierto |
| **Capacidad del taller** | Consulta y ajuste de la capacidad diaria del taller. | Cubierto |
| **Distribuidores** | Listado y búsqueda de distribuidores. | Cubierto |

## 3. Listado y Gestión de Órdenes

| Escenario | Descripción | Estado |
|---|---|---|
| **Listado por rol** | Cada portal muestra únicamente las órdenes correspondientes a su rol/permisos. | Cubierto |
| **Búsqueda** | Filtrado por número de orden, patente, vehículo o estado. | Cubierto |
| **Filtro por estado** | Filtrado por estado de orden con catálogo completo de estados. | Cubierto |
| **Paginación** | Navegación paginada con selector de tamaño (6/12/24). | Cubierto |
| **Filtros en URL** | Los filtros, búsqueda y paginación se sincronizan con la URL (compartibles). | Cubierto |
| **Filtros persistentes** | Persistencia en `localStorage` cuando no se usa sincronización con URL. | Cubierto |
| **Detalle de orden** | Acceso al detalle con información completa, bitácora, historial y evidencias. | Cubierto |

## 4. Acciones por Rol y Permisos

| Escenario | Descripción | Estado |
|---|---|---|
| **Reglas centralizadas** | Acciones determinadas por `accionesDisponibles()` en `OrderActions.ts` según rol y estado. | Cubierto |
| **Administrador** | Puede asignar mecánico (estado "Recibido") y registrar entrega (estado "Listo"). Las cancelaciones se confirman en la bandeja dedicada. | Cubierto |
| **Mecánico asignado** | Solo el mecánico asignado puede avanzar estados según transiciones permitidas. | Cubierto |
| **Mecánico no asignado** | Acciones bloqueadas con mensaje informativo. | Cubierto |
| **Cliente** | Puede gestionar presupuesto (estado "Pendiente de aprobación") o **solicitar** la cancelación de la orden en estados cancelables. | Cubierto |
| **Validación de motivo** | La solicitud de cancelación exige motivo obligatorio. | Cubierto |
| **Confirmación** | Acciones críticas requieren confirmación en diálogo modal. | Cubierto |
| **Sin acciones** | Cuando no hay acciones disponibles para el rol/estado, el panel no se muestra. | Cubierto |

## 5. Cancelaciones

| Escenario | Descripción | Estado |
|---|---|---|
| **Solicitud del cliente** | El cliente registra una solicitud de cancelación con motivo desde el detalle de la orden. | Cubierto |
| **Bandeja administrativa** | `/admin/cancelaciones` lista las solicitudes pendientes con orden, cliente, estado al solicitar y motivo. | Cubierto |
| **Confirmación administrativa** | El administrador confirma la cancelación desde la bandeja (exclusivo de su rol). | Cubierto |
| **Solo Administrador** | La consulta de pendientes y la confirmación se reservan al rol administrador. | Cubierto |
| **Sin acción directa del admin** | El detalle de la orden del administrador ya no ofrece "Cancelar": la confirmación vive en la bandeja. | Cubierto |

## 6. Clientes y Vehículos

| Escenario | Descripción | Estado |
|---|---|---|
| **Registro de vehículo** | El cliente registra un vehículo con patente, marca, modelo, año y kilometraje. | Cubierto |
| **Edición de vehículo** | El cliente edita marca, modelo, año y kilometraje desde `/client/vehiculos/:id/editar` (`PATCH /api/vehiculos/{id}`). La patente no se modifica. | Cubierto |
| **Pertenencia del vehículo** | La ficha del cliente solo muestra vehículos cuyo `clientId` coincide con la sesión. | Cubierto |
| **Historial por vehículo** | La ficha muestra el historial paginado de órdenes autorizado para el rol. | Cubierto |

## 7. Portal Cliente

| Escenario | Descripción | Estado |
|---|---|---|
| **Dashboard cliente** | Vista con vehículos, órdenes en proceso y presupuestos pendientes. | Cubierto |
| **Mis vehículos** | Listado, alta, edición y detalle de vehículos registrados con historial. | Cubierto |
| **Agendar mantención** | La ruta `/client/agendar` **no está implementada**: no existe endpoint de agenda y redirige a `/client/ordenes`. | No cubierto |
| **Mis órdenes** | Listado de órdenes propias con seguimiento. | Cubierto |
| **Presupuestos** | Listado y detalle de presupuestos con decisión (aprobar/rechazar) con motivo. | Cubierto |
| **Nuevas atenciones** | Listado y detalle de las solicitudes de nueva atención del cliente. | Cubierto |
| **Avisos** | Centro de notificaciones del cliente. | Cubierto |

## 8. Portal Mecánico

| Escenario | Descripción | Estado |
|---|---|---|
| **Panel mecánico** | Vista con órdenes asignadas y acceso a actualización de estados. | Cubierto |
| **Mis órdenes** | Listado filtrado por mecánico asignado. | Cubierto |
| **Actualizar estados** | Cambio de estado con transiciones validadas y restricción por asignación. | Cubierto |
| **Vehículos asignados** | Acceso a vehículos relacionados con órdenes asignadas. | Cubierto |
| **Presupuesto** | Edición del presupuesto desde el detalle de la orden asignada. | Cubierto |
| **Bitácora** | Registro de observaciones y acciones (con repuestos) contra la orden. | Cubierto |
| **Inventario de consulta** | El mecánico accede a catálogo, alertas, stock, umbral, movimientos y distribuidores en modo solo lectura. | Cubierto |
| **Movimientos de orden** | El mecánico registra únicamente `compromiso`, `consumo` o `liberación` con una orden asignada; no ve ingresos, ajustes ni proveedores. | Cubierto |

## 9. Inventario y Consumo de Repuestos

| Escenario | Descripción | Estado |
|---|---|---|
| **Inventario** | Listado de stock por repuesto con proveedor y estado. En el portal mecánico es solo lectura y agrega el enlace *Ver stock*. | Cubierto |
| **Alertas de stock** | Listado de repuestos bajo el umbral efectivo (consulta para mecánico y administrador). | Cubierto |
| **Movimientos** | Historial de movimientos con filtros y trazabilidad. El mecánico solo registra movimientos de sus órdenes asignadas. | Cubierto |
| **Detalle de stock** | Ficha de un repuesto con compromisos por orden (solo lectura). | Cubierto |
| **Umbral general** | Consulta e historial para ambos roles; el cambio del umbral queda reservado al administrador. | Cubierto |
| **Distribuidores** | Consulta del catálogo de proveedores; alta, edición y eliminación son exclusivas del administrador. | Cubierto |
| **Consumo de repuestos** | Panel en el detalle de la orden (Admin y Mecánico) para descontar los repuestos del presupuesto aprobado, solo en estados 4–6. | Cubierto |
| **Límite por ítem** | La cantidad máxima es `min(requerido, disponible)`; no se puede pedir más. | Cubierto |
| **Idempotencia** | Se usa `clave_operacion`; ante una respuesta incierta se conserva para reintentar sin duplicar, y se descarta ante rechazos definitivos. | Cubierto |
| **Stock insuficiente** | El `409` con `faltantes` se traduce y no descuenta nada (operación todo o nada); luego se refresca la disponibilidad. | Cubierto |
| **Sin presupuesto aprobado** | El panel avisa cuando la orden no tiene presupuesto aprobado del que consumir. | Cubierto |

## 10. Usuarios y Roles

| Escenario | Descripción | Estado |
|---|---|---|
| **Listado de usuarios** | `/admin/usuarios` lista las cuentas con sus roles y estado, con búsqueda por nombre/correo. | Cubierto |
| **Asignar rol** | Agrega un rol con `POST /auth/usuarios/{id}/roles` (idempotente, acumula roles). | Cubierto |
| **Retirar rol** | Quita un rol con `DELETE /auth/usuarios/{id}/roles/{rol}` (idempotente). | Cubierto |
| **Autoedición bloqueada** | El administrador no puede modificar los roles de su propia cuenta. | Cubierto |
| **Cuenta sin roles** | Dejar una cuenta con `roles: []` exige confirmación en diálogo. | Cubierto |
| **Fallo parcial** | Ante un error al guardar, se muestra el mensaje y se recarga el listado para reflejar el estado real. | Cubierto |

## 11. Evidencias y Presupuestos

| Escenario | Descripción | Estado |
|---|---|---|
| **Carga de evidencias** | Subida de evidencias con validación de tipo/tamaño. | Cubierto |
| **Listado de evidencias** | Visualización por contexto con galería. | Cubierto |
| **Presupuesto** | Creación, visualización y decisión por cliente. | Cubierto |
| **Aprobación/Rechazo** | Requiere validación y motivo en caso de rechazo. | Cubierto |

## 12. Estados de UI y Experiencia

| Escenario | Descripción | Estado |
|---|---|---|
| **Loading** | Skeletons y spinners durante carga de datos. | Cubierto |
| **Error con reintento** | Estados de error con botón de reintento. | Cubierto |
| **Empty state** | Mensajes diferenciados según filtros aplicados. | Cubierto |
| **Offline banner** | Aviso cuando no hay conexión. | Cubierto |
| **Accesibilidad** | Navegación por teclado, ARIA labels y skip links. | Cubierto |
| **Responsive** | Adaptación a diferentes tamaños de pantalla. | Cubierto |

## Cobertura de Pruebas

Las pruebas funcionales se encuentran en:
- `frontend/src/presentation/routes/AppRoutes.test.tsx` - Navegación por roles
- `frontend/src/presentation/components/orders/OrderActionsPanel.test.tsx` - Acciones por permisos
- `frontend/src/presentation/components/orders/ConsumoRepuestosPanel.test.tsx` - Consumo de repuestos, idempotencia y `409`
- `frontend/src/presentation/pages/admin/AdminCancelacionesPage.test.tsx` - Bandeja de cancelaciones
- `frontend/src/presentation/pages/admin/AdminUsersPage.test.tsx` - Gestión de roles y guardas
- `frontend/src/presentation/pages/admin/AdminInventoryPage.test.tsx` - Catálogo y modo mecánico
- `frontend/src/presentation/pages/admin/AdminInventoryMovementsPage.test.tsx` - Movimientos y restricciones del mecánico
- `frontend/src/presentation/pages/admin/AdminThresholdPage.test.tsx` - Umbral general y modo mecánico
- `frontend/src/presentation/pages/admin/AdminDistributorsPage.test.tsx` - Distribuidores y modo mecánico
- `frontend/src/presentation/pages/client/ClientVehicleEditPage.test.tsx` - Edición de vehículo
- `frontend/src/presentation/pages/admin/AdminDashboardPage.test.tsx` - Dashboard administrativo
- `frontend/src/presentation/hooks/useOrderListFilters.test.ts` (si aplica) - Filtros y paginación
- Pruebas unitarias de componentes UI y utilidades
