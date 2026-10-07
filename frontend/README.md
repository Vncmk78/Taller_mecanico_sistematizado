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
| `/client/ordenes` (+ `/:id`), `/client/presupuestos` | Órdenes del cliente / Presupuestos | Funcional / Placeholder |
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