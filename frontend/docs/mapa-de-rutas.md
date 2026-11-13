# Mapa de rutas del frontend

Documenta las rutas de la aplicación web `frontend/` (React + Vite + TypeScript
con React Router). Todas las rutas se definen en un único lugar:

`src/presentation/routes/AppRoutes.tsx`

## Modelos de protección

| Guard | Ruta | Comportamiento |
| --- | --- | --- |
| `PublicOnlyRoute` | `/login`, `/registro` | Si ya hay sesión, redirige al portal según el rol. |
| `ProtectedRoute` (con `allowedRoles`) | `/admin/*`, `/client/*`, `/mechanic/*` | Sin sesión → `/login`; rol no permitido → portal propio del rol. |
| `ClientProfileGate` | `/client/*` | Exige que la cuenta tenga perfil de cliente en MS2 antes de entrar al portal. |
| `*` (fallback) | cualquier ruta no definida | `Navigate to="/"` (landing). |
| Pública sin guard | `/`, `/acceso-denegado` | Accesibles sin sesión. |

Roles del sistema: `administrador`, `cliente`, `mecanico`.

## Árbol de rutas

```
/
├── /                         → Landing
├── /login                    → Inicio de sesión (PublicOnlyRoute)
├── /registro                 → Registro público de cliente (PublicOnlyRoute)
├── /acceso-denegado          → Error 403
│
├── /admin  (solo administrador, AdminLayout/RoleLayout sidebar)
│   ├── /admin                → Dashboard (índice)
│   ├── /admin/ordenes        → Gestión de órdenes
│   ├── /admin/ordenes/:id    → Detalle de la orden
│   ├── /admin/ordenes/:id/presupuesto → Editor de presupuesto
│   ├── /admin/ordenes/:id/evidencias  → Evidencia multimedia (con carga)
│   ├── /admin/nuevas-atenciones       → Nuevas atenciones
│   ├── /admin/nuevas-atenciones/:id   → Detalle de nueva atención
│   ├── /admin/cancelaciones  → Cancelaciones pendientes
│   ├── /admin/usuarios       → Usuarios y roles
│   ├── /admin/clientes       → Clientes
│   ├── /admin/configuracion  → Capacidad del taller
│   ├── /admin/vehiculos      → Catálogo de vehículos
│   ├── /admin/vehiculos/:id  → Ficha técnica del vehículo
│   ├── /admin/inventario     → Inventario
│   ├── /admin/inventario/alertas          → Alertas de stock
│   ├── /admin/inventario/movimientos      → Movimientos de inventario
│   ├── /admin/inventario/stock/:repuestoId → Detalle de stock
│   ├── /admin/inventario/umbral           → Umbral general
│   ├── /admin/distribuidores → Distribuidores
│   └── /admin/notificaciones → Centro de avisos
│
├── /client  (solo cliente, ClientLayout/RoleLayout topnav + ClientProfileGate)
│   ├── /client               → Dashboard (índice)
│   ├── /client/vehiculos     → Mis vehículos
│   ├── /client/vehiculos/nuevo → Registro de vehículo
│   ├── /client/vehiculos/:id → Detalle del vehículo
│   ├── /client/vehiculos/:id/editar → Edición de vehículo
│   ├── /client/agendar       → No implementada (redirige a /client/ordenes)
│   ├── /client/servicios     → Estado del servicio
│   ├── /client/ordenes       → Mis órdenes
│   ├── /client/ordenes/:id   → Detalle y seguimiento del servicio
│   ├── /client/ordenes/:id/evidencias → Evidencia multimedia del servicio
│   ├── /client/presupuestos  → Presupuestos
│   ├── /client/presupuestos/:ordenId → Detalle y decisión del presupuesto
│   ├── /client/nuevas-atenciones     → Nuevas atenciones
│   ├── /client/nuevas-atenciones/:id → Detalle de nueva atención
│   └── /client/notificaciones → Centro de avisos
│
└── /mechanic  (solo mecanico, MechanicLayout/RoleLayout sidebar)
    ├── /mechanic             → Panel (índice)
    ├── /mechanic/vehiculos   → Vehículos asignados
    ├── /mechanic/vehiculos/:id → Detalle del vehículo
    ├── /mechanic/ordenes     → Mis órdenes
    ├── /mechanic/ordenes/:id → Detalle de la orden
    ├── /mechanic/ordenes/:id/presupuesto → Editor de presupuesto
    ├── /mechanic/ordenes/:id/evidencias  → Evidencia multimedia (con carga)
    ├── /mechanic/estados     → Actualizar estados
    ├── /mechanic/inventario  → Catálogo de repuestos
    ├── /mechanic/inventario/alertas      → Alertas de stock
    ├── /mechanic/inventario/movimientos  → Movimientos de inventario
    ├── /mechanic/inventario/stock/:repuestoId → Detalle de stock
    ├── /mechanic/inventario/umbral       → Umbral general
    ├── /mechanic/inventario/distribuidores → Distribuidores
    └── /mechanic/notificaciones → Centro de avisos

* (cualquier otra ruta)      → / (fallback)
```

## Detalle por ruta

### Rutas públicas

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/` | `HomePage` | Funcional (landing) |
| `/login` | `LoginPage` | Funcional |
| `/registro` | `RegisterPage` | Funcional (registro público de cliente) |
| `/acceso-denegado` | `AccessDeniedPage` | Funcional (403) |

### Portal administrador (`/admin`)

Layout: `AdminLayout` → `RoleLayout` (variante `sidebar`). Aplica
`ProtectedRoute allowedRoles={['administrador']}`.

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/admin` | `AdminDashboardPage` | Funcional |
| `/admin/ordenes` | `AdminOrdersPage` | Funcional (listado, búsqueda, filtros y paginación) |
| `/admin/ordenes/:id` | `AdminOrderDetailPage` | Funcional (acciones con confirmación, consumo de repuestos y evidencia) |
| `/admin/ordenes/:id/presupuesto` | `BudgetEditor` | Funcional (edición de presupuesto) |
| `/admin/ordenes/:id/evidencias` | `OrderEvidencePage` | Funcional (subida con progreso/éxito/error) |
| `/admin/nuevas-atenciones` | `AdminNuevasAtencionesPage` | Funcional |
| `/admin/nuevas-atenciones/:id` | `AdminNuevaAtencionDetailPage` | Funcional |
| `/admin/cancelaciones` | `AdminCancelacionesPage` | Funcional (bandeja de solicitudes y confirmación) |
| `/admin/usuarios` | `AdminUsersPage` | Funcional (asignación/retiro de roles) |
| `/admin/clientes` | `AdminClientsPage` | Funcional (listado y búsqueda) |
| `/admin/configuracion` | `AdminConfigurationPage` | Funcional (capacidad del taller) |
| `/admin/vehiculos` | `AdminVehiclesPage` | Funcional |
| `/admin/vehiculos/:id` | `AdminVehicleDetailPage` | Funcional |
| `/admin/inventario` | `AdminInventoryPage` | Funcional |
| `/admin/inventario/alertas` | `AdminInventoryAlertsPage` | Funcional |
| `/admin/inventario/movimientos` | `AdminInventoryMovementsPage` | Funcional (trazabilidad) |
| `/admin/inventario/stock/:repuestoId` | `AdminStockDetailPage` | Funcional |
| `/admin/inventario/umbral` | `AdminThresholdPage` | Funcional |
| `/admin/distribuidores` | `AdminDistributorsPage` | Funcional |
| `/admin/notificaciones` | `NotificationsPage` | Funcional |

### Portal cliente (`/client`)

Layout: `ClientLayout` → `RoleLayout` (variante `topnav`). Aplica
`ProtectedRoute allowedRoles={['cliente']}` y `ClientProfileGate` (perfil MS2).

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/client` | `ClientDashboardPage` | Funcional |
| `/client/vehiculos` | `ClientVehiclesPage` | Funcional |
| `/client/vehiculos/nuevo` | `ClientVehicleFormPage` | Funcional |
| `/client/vehiculos/:id` | `ClientVehicleDetailPage` | Funcional |
| `/client/vehiculos/:id/editar` | `ClientVehicleEditPage` | Funcional (edición de marca, modelo, año y kilometraje) |
| `/client/agendar` | `Navigate` a `/client/ordenes` | **No implementada**: no existe endpoint de agenda; la ruta redirige en lugar de ofrecer un formulario |
| `/client/servicios` | `ClientServicesPage` | Funcional |
| `/client/ordenes` | `ClientOrdersPage` | Funcional |
| `/client/ordenes/:id` | `ClientOrderDetailPage` | Funcional (seguimiento y solicitud de cancelación) |
| `/client/ordenes/:id/evidencias` | `ClientOrderEvidencePage` | Funcional (solo lectura) |
| `/client/presupuestos` | `ClientBudgetsPage` | Funcional |
| `/client/presupuestos/:ordenId` | `ClientBudgetDetailPage` | Funcional (decisión de presupuesto con confirmación) |
| `/client/nuevas-atenciones` | `ClientNuevasAtencionesPage` | Funcional |
| `/client/nuevas-atenciones/:id` | `ClientNuevaAtencionDetailPage` | Funcional |
| `/client/notificaciones` | `NotificationsPage` | Funcional |

### Portal mecánico (`/mechanic`)

Layout: `MechanicLayout` → `RoleLayout` (variante `sidebar`). Aplica
`ProtectedRoute allowedRoles={['mecanico']}`.

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/mechanic` | `MechanicDashboardPage` | Funcional (indicadores calculados en el cliente) |
| `/mechanic/vehiculos` | `MechanicVehiclesPage` | Funcional |
| `/mechanic/vehiculos/:id` | `MechanicVehicleDetailPage` | Funcional |
| `/mechanic/ordenes` | `MechanicOrdersPage` | Funcional |
| `/mechanic/ordenes/:id` | `MechanicOrderDetailPage` | Funcional (acciones con confirmación, consumo de repuestos, bitácora y evidencia) |
| `/mechanic/ordenes/:id/presupuesto` | `MechanicBudgetPage` | Funcional (edición de presupuesto) |
| `/mechanic/ordenes/:id/evidencias` | `OrderEvidencePage` | Funcional (subida con progreso/éxito/error) |
| `/mechanic/estados` | `MechanicStatusPage` | Funcional (avance de estado con confirmación) |
| `/mechanic/inventario` | `AdminInventoryPage` (`mode="mechanic"`) | Funcional (solo lectura; enlace a stock) |
| `/mechanic/inventario/alertas` | `AdminInventoryAlertsPage` | Funcional (solo lectura) |
| `/mechanic/inventario/movimientos` | `AdminInventoryMovementsPage` (`mode="mechanic"`) | Funcional (consulta y movimientos de órdenes asignadas) |
| `/mechanic/inventario/stock/:repuestoId` | `AdminStockDetailPage` | Funcional (solo lectura) |
| `/mechanic/inventario/umbral` | `AdminThresholdPage` (`mode="mechanic"`) | Funcional (solo lectura) |
| `/mechanic/inventario/distribuidores` | `AdminDistributorsPage` (`mode="mechanic"`) | Funcional (solo lectura) |
| `/mechanic/notificaciones` | `NotificationsPage` | Funcional |

## Menús por rol

Los ítems de navegación se declaran en cada layout (`AdminLayout`,
`ClientLayout`, `MechanicLayout`) y los renderiza el componente reutilizable
`RoleLayout` (`SidebarNav` para variante `sidebar`, `TopBar` para `topnav`).

**Administrador** (sidebar):
- Portal Administrador: *Panel de Control* (`/admin`), *Gestión de Órdenes* (`/admin/ordenes`), *Nuevas atenciones* (`/admin/nuevas-atenciones`), *Cancelaciones pendientes* (`/admin/cancelaciones`), *Clientes* (`/admin/clientes`), *Usuarios y roles* (`/admin/usuarios`), *Capacidad del taller* (`/admin/configuracion`), *Centro de avisos* (`/admin/notificaciones`).
- Catálogo: *Vehículos* (`/admin/vehiculos`), *Inventario* (`/admin/inventario`), *Alertas de stock* (`/admin/inventario/alertas`), *Movimientos* (`/admin/inventario/movimientos`), *Umbral general* (`/admin/inventario/umbral`), *Distribuidores* (`/admin/distribuidores`).

**Cliente** (topnav):
- *Mi Portal* (`/client`), *Mis Vehículos* (`/client/vehiculos`), *Estado del Servicio* (`/client/servicios`), *Mis Órdenes* (`/client/ordenes`), *Presupuestos* (`/client/presupuestos`), *Nuevas Atenciones* (`/client/nuevas-atenciones`), *Avisos* (`/client/notificaciones`).
- No hay ítem de menú para *Agendar Mantención*: `/client/agendar` no está implementada y redirige a *Mis Órdenes*.

**Mecánico** (sidebar):
- Portal Mecánico: *Mi Panel* (`/mechanic`), *Mis Órdenes* (`/mechanic/ordenes`), *Actualizar Estados* (`/mechanic/estados`), *Vehículos Asignados* (`/mechanic/vehiculos`), *Centro de avisos* (`/mechanic/notificaciones`).
- Inventario: *Repuestos* (`/mechanic/inventario`), *Alertas de stock* (`/mechanic/inventario/alertas`), *Movimientos* (`/mechanic/inventario/movimientos`), *Umbral general* (`/mechanic/inventario/umbral`), *Distribuidores* (`/mechanic/inventario/distribuidores`).

## Reglas de navegación

1. Sin sesión en una ruta protegida → redirige a `/login` (`ProtectedRoute` conserva `state.from` para volver tras el login).
2. Sesión con rol incorrecto → redirige al portal propio del rol.
3. Usuario con sesión en `/login` o `/registro` → redirige a su portal (`PublicOnlyRoute`).
4. Ruta inexistente → `/` (fallback `*`).
5. Tras `logout` → `/login`.

## Notas

- Las vistas de vehículos (`/admin/vehiculos*`, `/client/vehiculos*`,
  `/mechanic/vehiculos*`) consumen `useVehicleStore`, que se alimenta solo de
  respuestas reales de la Gateway (MS2). Los datos mock viven únicamente en los
  tests (`infrastructure/mocks/`).
- **Edición de vehículo (cliente)**: `/client/vehiculos/:id/editar` reutiliza el
  formulario compartido `VehicleForm` y envía `PATCH /api/vehiculos/{id}` con
  `marca`, `modelo`, `anio` y `kilometraje`. La patente no se modifica porque el
  contrato del endpoint no la acepta.
- **Cancelaciones**: el cliente solo *solicita* la cancelación desde el detalle
  de su orden. La confirmación es exclusiva del Administrador y se realiza en
  `/admin/cancelaciones` (no hay acción de cancelación en el detalle de la orden
  del administrador).
- **Consumo de repuestos**: disponible en `/admin/ordenes/:id` y
  `/mechanic/ordenes/:id` mientras la orden está en taller (estados 4–6). El
  panel `ConsumoRepuestosPanel` usa la disponibilidad del presupuesto aprobado,
  envía una `clave_operacion` idempotente y maneja el `409` con `faltantes`.
- **Inventario del mecánico**: `/mechanic/inventario*` reutiliza las pantallas de
  inventario con `mode="mechanic"`. El mecánico consulta catálogo, alertas,
  movimientos, stock, umbral e historial y distribuidores, pero no ve las
  acciones administrativas (crear/editar/eliminar repuestos o proveedores,
  ingresos, ajustes ni cambio de umbral). En movimientos solo puede registrar
  `compromiso`, `consumo` o `liberación` con una orden asignada; el backend
  valida esa asignación. El modo del portal manda incluso si la cuenta acumula
  también el rol `administrador`.
- **Gestión de roles**: `/admin/usuarios` acumula y retira roles con
  `POST/DELETE /auth/usuarios/{id}/roles`. La propia cuenta del administrador no
  se puede editar y se pide confirmación antes de dejar una cuenta sin roles.
- `/mechanic/historial` se eliminó: no existe endpoint de historial por mecánico
  (MS2 solo expone `GET /api/ordenes/{id}/historial`) y el historial completo ya
  se consulta en `/mechanic/ordenes/:id`.
- La bitácora de trabajo (`OrderBitacoraSection`) vive dentro de
  `/mechanic/ordenes/:id`: no tiene ruta propia. El mecánico registra
  observaciones y acciones (con repuestos) contra `POST /api/ordenes/{id}/bitacora`
  y todos los roles la consultan con `GET /api/ordenes/{id}/bitacora`.
- `MechanicHistoryPage.tsx`, `MechanicPortalPage.tsx` y `ClientPortalPage.tsx`
  se eliminaron por no tener rutas asociadas. El inicio del cliente utiliza
  `ClientDashboardPage.tsx`.
- El portal del mecánico acota sus datos en dos barreras: la Gateway ya devuelve
  solo lo asignado al mecánico, y las vistas comparan contra `user.id`
  (`mechanicScope.ts`). Además `logout`/`clearSession` purgan las cachés
  compartidas de órdenes y vehículos.
- La **evidencia multimedia** del personal reutiliza `OrderEvidenceSection` en
  el detalle de la orden (Admin y Mecánico) y `OrderEvidencePage` en la ruta
  propia `/…/ordenes/:id/evidencias`. La subida (Mecánico/Administrador) muestra
  progreso real, éxito y error; el Cliente solo ve
  `/client/ordenes/:id/evidencias` en modo lectura.
