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
| `/client/vehiculos` (+ `/nuevo`, `/:id`) | Mis vehículos y registro | Funcional |
| `/client/agendar` | Agendar mantención | Provisional "Próximamente" |
| `/client/servicios`, `/presupuestos` | Secciones cliente | Placeholder |
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