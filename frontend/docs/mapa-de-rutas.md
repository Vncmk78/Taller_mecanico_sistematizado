# Mapa de rutas del frontend

Documenta las rutas de la aplicación web `frontend/` (React + Vite + TypeScript
con React Router). Todas las rutas se definen en un único lugar:

`src/presentation/routes/AppRoutes.tsx`

## Modelos de protección

| Guard | Ruta | Comportamiento |
| --- | --- | --- |
| `PublicOnlyRoute` | `/login` | Si ya hay sesión, redirige al portal según el rol. |
| `ProtectedRoute` (con `allowedRoles`) | `/admin/*`, `/client/*`, `/mechanic/*` | Sin sesión → `/login`; rol no permitido → portal propio del rol. |
| `*` (fallback) | cualquier ruta no definida | `Navigate to="/"` (landing). |
| Pública sin guard | `/`, `/acceso-denegado` | Accesibles sin sesión. |

Roles del sistema: `administrador`, `cliente`, `mecanico`.

## Árbol de rutas

```
/
├── /                         → Landing
├── /login                    → Inicio de sesión (PublicOnlyRoute)
├── /acceso-denegado          → Error 403
│
├── /admin  (solo administrador, AdminLayout/RoleLayout sidebar)
│   ├── /admin                → Dashboard (índice)
│   ├── /admin/ordenes        → Gestión de Órdenes
│   ├── /admin/clientes       → Clientes
│   ├── /admin/vehiculos      → Catálogo de vehículos
│   ├── /admin/vehiculos/:id  → Ficha técnica del vehículo
│   ├── /admin/inventario     → Inventario
│   └── /admin/distribuidores → Distribuidores
│
├── /client  (solo cliente, ClientLayout/RoleLayout topnav)
│   ├── /client               → Dashboard (índice)
│   ├── /client/vehiculos     → Mis Vehículos
│   ├── /client/vehiculos/nuevo → Registro de vehículo
│   ├── /client/vehiculos/:id → Detalle del vehículo
│   ├── /client/agendar       → Agendar Mantención (provisional)
│   ├── /client/servicios     → Estado del Servicio
│   └── /client/presupuestos  → Presupuestos
│
└── /mechanic  (solo mecanico, MechanicLayout/RoleLayout sidebar)
    ├── /mechanic             → Dashboard (índice)
    ├── /mechanic/vehiculos   → Vehículos asignados
    ├── /mechanic/vehiculos/:id → Detalle del vehículo
    ├── /mechanic/ordenes     → Mis Órdenes
    ├── /mechanic/estados     → Actualizar Estados
    └── /mechanic/historial   → Actividades

* (cualquier otra ruta)      → / (fallback)
```

## Detalle por ruta

### Rutas públicas

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/` | `HomePage` | Funcional (landing) |
| `/login` | `LoginPage` | Funcional |
| `/acceso-denegado` | `AccessDeniedPage` | Funcional (403) |

### Portal administrador (`/admin`)

Layout: `AdminLayout` → `RoleLayout` (variante `sidebar`). Aplica
`ProtectedRoute allowedRoles={['administrador']}`.

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/admin` | `AdminDashboardPage` | Funcional |
| `/admin/ordenes` | `AdminOrdersPage` | Placeholder ("Estructura en construcción") |
| `/admin/clientes` | `AdminClientsPage` | Placeholder |
| `/admin/vehiculos` | `AdminVehiclesPage` | Funcional |
| `/admin/vehiculos/:id` | `AdminVehicleDetailPage` | Funcional |
| `/admin/inventario` | `AdminInventoryPage` | Placeholder |
| `/admin/distribuidores` | `AdminDistributorsPage` | Placeholder |

### Portal cliente (`/client`)

Layout: `ClientLayout` → `RoleLayout` (variante `topnav`). Aplica
`ProtectedRoute allowedRoles={['cliente']}`.

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/client` | `ClientDashboardPage` | Funcional |
| `/client/vehiculos` | `ClientVehiclesPage` | Funcional |
| `/client/vehiculos/nuevo` | `ClientVehicleFormPage` | Funcional |
| `/client/vehiculos/:id` | `ClientVehicleDetailPage` | Funcional |
| `/client/agendar` | `div` inline en `AppRoutes` | Provisional ("Próximamente") |
| `/client/servicios` | `ClientServicesPage` | Placeholder |
| `/client/presupuestos` | `ClientBudgetsPage` | Placeholder |

### Portal mecánico (`/mechanic`)

Layout: `MechanicLayout` → `RoleLayout` (variante `sidebar`). Aplica
`ProtectedRoute allowedRoles={['mecanico']}`.

| Ruta | Componente | Estado |
| --- | --- | --- |
| `/mechanic` | `MechanicDashboardPage` | Funcional |
| `/mechanic/vehiculos` | `MechanicVehiclesPage` | Funcional |
| `/mechanic/vehiculos/:id` | `MechanicVehicleDetailPage` | Funcional |
| `/mechanic/ordenes` | `MechanicOrdersPage` | Placeholder |
| `/mechanic/estados` | `MechanicStatusPage` | Placeholder |
| `/mechanic/historial` | `MechanicHistoryPage` | Placeholder |

## Menús por rol

Los ítems de navegación se declaran en cada layout (`AdminLayout`,
`ClientLayout`, `MechanicLayout`) y los renderiza el componente reutilizable
`RoleLayout` (`SidebarNav` para variante `sidebar`, `TopBar` para `topnav`).

**Administrador** (sidebar):
- Portal Administrador: *Panel de Control* (`/admin`), *Gestión de Órdenes* (`/admin/ordenes`), *Clientes* (`/admin/clientes`).
- Catálogo: *Vehículos* (`/admin/vehiculos`), *Inventario* (`/admin/inventario`), *Distribuidores* (`/admin/distribuidores`).

**Cliente** (topnav):
- *Mi Portal* (`/client`), *Mis Vehículos* (`/client/vehiculos`), *Agendar Mantención* (`/client/agendar`), *Estado del Servicio* (`/client/servicios`), *Presupuestos* (`/client/presupuestos`).

**Mecánico** (sidebar):
- *Mi Panel* (`/mechanic`), *Mis Órdenes* (`/mechanic/ordenes`), *Actualizar Estados* (`/mechanic/estados`), *Actividades* (`/mechanic/historial`), *Vehículos Asignados* (`/mechanic/vehiculos`).

## Reglas de navegación

1. Sin sesión en una ruta protegida → redirige a `/login` (`ProtectedRoute` conserva `state.from` para volver tras el login).
2. Sesión con rol incorrecto → redirige al portal propio del rol.
3. Usuario con sesión en `/login` → redirige a su portal (`PublicOnlyRoute`).
4. Ruta inexistente → `/` (fallback `*`).
5. Tras `logout` → `/login`.

## Notas

- Las vistas de vehículos (`/admin/vehiculos*`, `/client/vehiculos*`,
  `/mechanic/vehiculos*`) consumen `useVehicleStore`: usan datos mock mientras
  el servicio de vehículos (MS2 vía Gateway) no esté disponible.
- `ClientPortalPage.tsx` y `MechanicPortalPage.tsx` son páginas heredadas que
  ya no tienen rutas asociadas (candidatas a eliminar).
- Las rutas de vehículos y sus componentes los aportó el resto del equipo y se
  integraron en la promoción a `main` (commit de merge `ea2b439`).