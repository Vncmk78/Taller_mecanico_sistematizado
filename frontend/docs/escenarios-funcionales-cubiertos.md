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

## 2. Panel Administrativo

| Escenario | Descripción | Estado |
|---|---|---|
| **Panel inicial** | Acceso al dashboard con resumen operativo (órdenes totales/activas, vehículos, mecánicos, estados). | Cubierto |
| **Carga de indicadores** | Muestra estado de carga mientras se obtienen los datos. | Cubierto |
| **Manejo de errores** | Muestra `ErrorState` con botón "Reintentar" ante fallos en la carga del resumen. | Cubierto |
| **Carga de mecánicos** | Visualización de mecánicos con sus órdenes totales y activas, ordenados por carga. | Cubierto |
| **Paginación** | Paginación de la carga de mecánicos (5 por página) con navegación y contador. | Cubierto |
| **Navegación del panel** | Acceso a órdenes, clientes, vehículos, inventario y distribuidores desde el menú lateral. | Cubierto |

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
| **Administrador** | Puede asignar mecánico (estado "Recibido"), cancelar órdenes cancelables y registrar entrega (estado "Listo"). | Cubierto |
| **Mecánico asignado** | Solo el mecánico asignado puede avanzar estados según transiciones permitidas. | Cubierto |
| **Mecánico no asignado** | Acciones bloqueadas con mensaje informativo. | Cubierto |
| **Cliente** | Puede gestionar presupuesto (estado "Pendiente de aprobación") o cancelar solicitud en estados cancelables. | Cubierto |
| **Validación de motivo** | Cancelación exige motivo obligatorio. | Cubierto |
| **Confirmación** | Acciones críticas requieren confirmación en diálogo modal. | Cubierto |
| **Sin acciones** | Cuando no hay acciones disponibles para el rol/estado, el panel no se muestra. | Cubierto |

## 5. Portal Cliente

| Escenario | Descripción | Estado |
|---|---|---|
| **Dashboard cliente** | Vista con vehículos, órdenes en proceso y presupuestos pendientes. | Cubierto |
| **Mis vehículos** | Listado y detalle de vehículos registrados con historial. | Cubierto |
| **Agendar mantención** | Formulario para agendar mantención. | Cubierto |
| **Mis órdenes** | Listado de órdenes propias con seguimiento. | Cubierto |
| **Presupuestos** | Listado y detalle de presupuestos con decisión (aprobar/rechazar) con motivo. | Cubierto |

## 6. Portal Mecánico

| Escenario | Descripción | Estado |
|---|---|---|
| **Panel mecánico** | Vista con órdenes asignadas y acceso a actualización de estados. | Cubierto |
| **Mis órdenes** | Listado filtrado por mecánico asignado. | Cubierto |
| **Actualizar estados** | Cambio de estado con transiciones validadas y restricción por asignación. | Cubierto |
| **Vehículos asignados** | Acceso a vehículos relacionados con órdenes asignadas. | Cubierto |

## 7. Evidencias y Presupuestos

| Escenario | Descripción | Estado |
|---|---|---|
| **Carga de evidencias** | Subida de evidencias con validación de tipo/tamaño. | Cubierto |
| **Listado de evidencias** | Visualización por contexto con galería. | Cubierto |
| **Presupuesto** | Creación, visualización y decisión por cliente. | Cubierto |
| **Aprobación/Rechazo** | Requiere validación y motivo en caso de rechazo. | Cubierto |

## 8. Estados de UI y Experiencia

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
- `frontend/src/presentation/pages/admin/AdminDashboardPage.test.tsx` - Dashboard administrativo
- `frontend/src/presentation/hooks/useOrderListFilters.test.ts` (si aplica) - Filtros y paginación
- Pruebas unitarias de componentes UI y utilidades
