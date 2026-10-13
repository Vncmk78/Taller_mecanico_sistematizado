# Frontend — Sistema de Gestión de Talleres Mecánicos

Aplicación web del proyecto "Taller de Integración II" (UCT), desarrollada por
**Gustavo** en la rama `Gustavo`.

React 19 + Vite + TypeScript, con **Tailwind CSS v4** (tema dark glassmorphism)
y arquitectura hexagonal.

## ¿Qué se ha hecho?

### Tarea 1 — Estructura del proyecto React
- Proyecto React + Vite + TypeScript creado desde cero en `frontend/`.
- Organización por **arquitectura hexagonal**:
  - `src/domain/` → entidades (`User`, `Vehicle`, `Order`) y puertos (`AuthPort`).
  - `src/application/` → casos de uso (en preparación).
  - `src/infrastructure/` → cliente HTTP (`apiClient` con Axios e
    interceptores de JWT), estado global de autenticación (`Zustand`).
  - `src/presentation/` → componentes UI, layouts, páginas y rutas.
- Sistema de rutas con React Router (`/`, `/login`, `/admin/*`, `/client`,
  `/mechanic`).
- Tema Tailwind v4 con colores y estilos basados en los prototipos del diseño.

### Tarea 2 — Interfaz de inicio de sesión
- Vista de login con formulario validado con **React Hook Form + Zod**.
- Manejo de estados de carga y errores (mensajes de error desde la API).
- Directamente conectado a la **API Gateway**:
  - Adaptador `AuthService` (`infrastructure/api`) que implementa el puerto `AuthPort`.
  - Envía `POST /auth/login` a la Gateway (por defecto `http://localhost:8000/api`),
    guarda el JWT y redirige según el rol del usuario: admin → `/admin`,
    cliente → `/client`, mecánico → `/mechanic`.
- Cierre de sesión desde el panel de administrador.

### Extras
- Panel de administrador: layout con sidebar y dashboard de ejemplo
  (estadísticas, cola de trabajo, actividad reciente).
- Skills de desarrollo (`src/skills/`) para el flujo de trabajo asistido
  (excluidas del control de versiones).

### Tarea 3 — Implementar gestión de sesión, token y rutas protegidas
- **Restauración de sesión**: al abrir la app se valida el token guardado con
  `GET /auth/me` y se carga el usuario (`restoreSession`). Token inválido → se
  limpia la sesión.
- **Rutas protegidas**: componente `ProtectedRoute` que redirige a `/login`
  si no hay sesión válida y valida el rol (admin → `/admin/*`, cliente →
  `/client`, mecánico → `/mechanic`).
- **Redirección de retorno**: tras iniciar sesión vuelve a la ruta que se
  intentaba abrir (mantiene el `state.from`).
- Pantalla de carga mientras se verifica la sesión.

### Tarea 5 — Implementar vistas del cliente para consultar vehículos y servicios
- **Estado del Servicio** (`/client/servicios`): vista funcional de consulta de
  los servicios del cliente con su estado en tiempo real. Agrupa las órdenes en
  *Requieren su atención* (presupuesto por aprobar, estado 3), *En proceso*
  y *Finalizados*, usando la API de órdenes de MS2 con fallback local.
  Componente `ServiceCard` para cada servicio con acceso al detalle de la orden
  y la ficha del vehículo.
- **Ficha técnica del vehículo** (`/client/vehiculos/:id`): el historial de
  órdenes del vehículo ahora se consulta de las órdenes del cliente (con su
  estado y fecha de actualización) y enlaza al detalle de cada orden.

### Tarea 6 — Implementar estados vacío, carga y error en las vistas del cliente
- **Estado del Servicio** (`/client/servicios`): estados de carga
  (`OrderListSkeleton`), vacío (sin servicios registrados), *offline con caché*
  (banner + datos locales) y **error sin datos en caché** (bloque con mensaje y
  botón *Reintentar*).
- **Ficha técnica del vehículo** (`/client/vehiculos/:id`): estados de carga,
  vehículo no encontrado o ajeno, **error al cargar los datos del vehículo**
  (distinto de "no encontrado", con reintento) y **error al cargar el historial
  de órdenes** (con reintento), además del banner *offline* con datos de caché.

### Tarea 7 — Revisar comportamiento responsive de las vistas implementadas
- **Portal Cliente (topnav)**: navegación con scroll horizontal en pantallas
  angostas, badge y datos del usuario plegados en móvil, y padding del header
  reducido en breakpoints chicos.
- **Estado del Servicio** (`/client/servicios`): columnas de tarjetas que pasan a
  1 columna en móvil (`sm:grid-cols-2`), padding del contenedor y de los estados
  vacío/error adaptado (`p-5 sm:p-8 lg:p-10` / `p-8 sm:p-14`).
- **Ficha técnica del vehículo** (`/client/vehiculos/:id`): el detalle apila la
  ficha bajo el historial en pantallas menores a `lg`, con el mismo padding
  adaptado; `VehicleInfoPanel` permite envolver título/patente y `ServiceCard`
  mantiene el badge fijo frente al título truncado.

### Tarea 8 — Crear pruebas de visualización de información según cliente autenticado
- Pruebas de que el portal Cliente muestra información según la **identidad de la
  sesión** (`user.id`), no según el cliente demo:
  - **Ficha del vehículo**: un vehículo cuyo `clientId` no calza con el
    autenticado se oculta ("Vehículo no encontrado o no pertenece a su cuenta") y
    el control de pertenencia usa el id de la sesión.
  - **Estado del Servicio / Mis Órdenes**: en *offline*, el filtro por vehículos
    del cliente usa al cliente autenticado (no el demo `c1`).
  - **Panel del cliente** (`/client`): saluda con `full_name` del autenticado.
  - **Layout topnav**: muestra la identidad (nombre/email) del usuario de sesión.

### Tarea 9 — Implementar detalle de estado y seguimiento del servicio
- **`/client/ordenes/:id`** (reutilizado por "Ver detalle" en Estado del Servicio):
  complementa el panel de la orden con el seguimiento completo del servicio:
  - **Ciclo de estados** (stepper) con el estado actual destacado (`aria-current`).
  - **Historial de cambios** con fechas, responsable y observaciones
    (`GET /api/ordenes/{id}/historial` vía `orderService.getOrderHistory`, con caché
    en `useOrderHistoryStore`).
  - Estados robustos: *loading*, **404 real** ("Orden no encontrada." con regreso a
    mis órdenes) y **error de servidor / sin conexión**, que ya no se disfraza de
    "no encontrada" y ofrece Reintentar. Sin conexión conserva el detalle y el
    seguimiento desde la caché compartida mostrando el banner offline.
- Padding responsive (`p-5 sm:p-8 lg:p-10`) consistente con el resto del portal.
- Pruebas nuevas en `ClientServiceTracking.test.tsx` (estado actual + historial,
  404 vs 500, offline con caché y error con caché) sin modificar los tests de
  detalle ya existentes.

### Tarea 10 — Crear componente reutilizable para mostrar estado e historial de la orden
- **`OrderStatusAndHistory`** (`presentation/components/orders/OrderStatusAndHistory.tsx`)
  es el componente reutilizable que muestra el **estado** (stepper del ciclo de 8
  estados con la etapa actual marcada con `aria-current`) y el **historial**
  (timeline con fechas, responsable y observaciones) de una orden a partir de un
  único contrato: la prop `order`. Se incrusta en las vistas de detalle de los
  3 portales: `ClientOrderDetailPage`, `AdminOrderDetailPage` y
  `MechanicOrderDetailPage`.
  - **Fuente de datos**: `useOrderHistory` → `OrderService.getOrderHistory`
    (`GET /api/ordenes/{id}/historial`) con caché compartida en
    `useOrderHistoryStore`.
  - **Comportamiento**: ante *offline* o error del servidor conserva el historial
    en caché y avisa con `OfflineBanner` (reintento incluido); sin registros
    muestra el estado vacío del timeline.
  - **Reuso garantizado por tests**: los del bloque (`OrderStateStepper`,
    `OrderHistoryTimeline`, `OrderStatusAndHistory`) más
    `OrderStatusAndHistory.reuse.test.tsx`, que fija el contrato de reuso y los
    casos offline/error con caché.
- El bloque se mantiene descompuesto por responsabilidad (S.O.L.I.D/Hexagonal):
  `OrderStateStepper` (ciclo), `OrderHistoryTimeline` (seguimiento) y
  `OrderStatusBadge` (etiqueta del estado).

### Tarea 11 — Implementar flujo visual de aprobación y rechazo de presupuesto
- **`/client/presupuestos`** (lista): muestra los presupuestos de las órdenes del
  cliente, destacando los que **esperan su decisión** (versión enviada pendiente)
  frente a los ya aprobados o rechazados. Como el contrato de MS3 no expone un
  listado global para el cliente, el listado se deriva de las órdenes del cliente
  y se resuelve cada una con `GET /api/presupuestos?orden_id={id}` (consultas en
  paralelo vía `useClientBudgets`/`useBudgetStore`).
- **`/client/presupuestos/:ordenId`** (detalle y decisión):
  - Trae el detalle con versiones e ítems (`GET /api/presupuestos/{id}`), muestra
    las **partidas** (repuesto / mano de obra) y el **total** en CLP.
  - **Aprobar** pide confirmación y envía
    `{ decision: "aprobado" }`.
  - **Rechazar** exige `motivo`; si se rechaza **antes de la primera aprobación**
    (cancela el servicio) además exige confirmar la cancelación, tal como lo
    declara el contrato (`confirmar_cancelacion`).
  - `201` refleja el nuevo estado en caché y muestra el **efecto en la orden**;
    `409/422` muestran el mensaje de negocio y `503` se informa como decisión
    guardada con aplicación pendiente (sin invitar a repetir la decisión).
- Componentes y utilidades: `BudgetStatusBadge`, `BudgetItemRow`, `BudgetCard`,
  `RejectBudgetDialog`; `formatMoneyCLP` (CLP sin decimales) y `EFECTO_EN_ORDEN_LABEL`.
- Estados de carga, vacío, *offline* con caché y error reintentable coherentes con
  el resto del portal.
- Pruebas: `PresupuestoService.test.ts` (mapeo del contrato),
  `ClientBudgetsPage.test.tsx` y `ClientBudgetDetailPage.test.tsx` (lista,
  aprobación, rechazo con motivo/cancelación y estados de error).

### Tarea 12 — Agregar confirmaciones y validaciones antes de aprobar o rechazar
- **Aprobar**: nuevo diálogo `ApproveBudgetDialog` que resume el **total** y la
  cantidad de partidas y exige marcar *"He revisado las partidas y el total"*
  antes de habilitar la confirmación (aprobar autoriza el cobro y no se deshace).
- **Rechazar**: el **motivo** ahora exige un mínimo de 5 caracteres (con contador),
  además de ser obligatorio; se conserva la confirmación de cancelación cuando
  rechazar cancela el servicio.
- **Versión vigente**: se recuerda la versión pendiente al abrir el diálogo y se
  compara antes de enviar; si cambió —o el backend responde `409`— **no** se envía
  la decisión obsoleta: se refresca el detalle y se avisa al cliente.
- **Sin conexión**: se bloquean aprobar y rechazar con un aviso (no se envía una
  decisión que el servidor no registraría). Un presupuesto **sin partidas** no se
  puede aprobar.
- **Doble envío**: la decisión queda bloqueada mientras hay una petición en curso.
- Pruebas: `ApproveBudgetDialog.test.tsx` y casos nuevos en
  `ClientBudgetDetailPage.test.tsx` (bloqueo de aprobación, conflicto `409` y
  decisiones bloqueadas sin conexión).

## ¿Qué puede hacer el sistema en estos momentos?

El mapa completo de rutas está documentado en
[`docs/mapa-de-rutas.md`](docs/mapa-de-rutas.md).

| Ruta | Vista | Estado |
| --- | --- | --- |
| `/` | Landing | Funcional |
| `/login` | Inicio de sesión | Funcional |
| `/admin` | Dashboard del administrador | Funcional (solo rol administrador) |
| `/admin/vehiculos` y `/admin/vehiculos/:id` | Catálogo y ficha del vehículo | Funcional |
| `/admin/ordenes`, `/clientes`, `/inventario`, `/distribuidores` | Secciones admin | Placeholder "Estructura en construcción" |
| `/client` | Portal Cliente (dashboard) | Funcional (solo rol cliente) |
| `/client/vehiculos` (+ `/nuevo`, `/:id`) | Mis vehículos, registro y ficha con historial de órdenes | Funcional |
| `/client/agendar` | Agendar mantención | Provisional "Próximamente" |
| `/client/servicios` | Estado del Servicio (consulta de servicios) | Funcional |
| `/client/ordenes` (+ `/:id`) | Órdenes del cliente y detalle de estado y seguimiento | Funcional |
| `/client/presupuestos` (+ `/:ordenId`) | Presupuestos: lista y detalle con aprobación/rechazo | Funcional |
| `/mechanic` | Portal Mecánico (dashboard) | Funcional (solo rol mecánico) |
| `/mechanic/vehiculos` (+ `/:id`) | Vehículos asignados | Funcional |
| `/mechanic/ordenes`, `/estados`, `/historial` | Secciones mecánico | Placeholder |

Nota: el login consume la **API Gateway** (`POST /auth/login`). Si ni la Gateway ni
el `auth-service` están desplegados, se muestra el error de credenciales. Las vistas
de vehículos usan datos mock mientras MS2 no esté disponible.

## Cómo ejecutar el proyecto localmente

Requisitos: **Node.js 18+**.

```bash
cd frontend
npm install
npm run dev
```

Se abre en: `http://localhost:5173`

### Variables de entorno

Crear un archivo `.env` en `frontend/` con:

```env
VITE_API_URL=http://localhost:8000/api
```

Si no se define, se usa `http://localhost:8000/api` por defecto.

### Otros comandos

```bash
npm run build   # compilar para producción (tsc + vite build)
npm run preview # previsualizar el build de producción
npm run lint    # análisis estático con Oxlint
```

## Arquitectura

```
frontend/
├── src/
│   ├── domain/          # Entidades y puertos (reglas de negocio)
│   ├── application/     # Casos de uso
│   ├── infrastructure/  # Axios, Zustand, config
│   ├── presentation/    # UI, layouts, páginas, rutas
│   └── skills/          # Skills de desarrollo (gitignored)
├── index.html
├── package.json
├── vite.config.ts       # Alias @ → src, plugin Tailwind
└── tsconfig.app.json    # Alias @/*
```