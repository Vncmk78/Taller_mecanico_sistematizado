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
- Manejo de estados de carga y errores.
- Integrado con el store de autenticación (**Zustand**) y el cliente HTTP
  (**Axios**): envía `POST /auth/login`, guarda el token JWT y redirige según rol.
- Cierre de sesión desde el panel de administrador.

### Extras
- Panel de administrador: layout con sidebar y dashboard de ejemplo
  (estadísticas, cola de trabajo, actividad reciente).
- Skills de desarrollo (`src/skills/`) para el flujo de trabajo asistido
  (excluidas del control de versiones).

## ¿Qué puede hacer el sistema en estos momentos?

| Ruta | Vista | Estado |
| --- | --- | --- |
| `/` | Landing (prototipo v1) | Funcional |
| `/login` | Inicio de sesión | Funcional |
| `/admin` | Dashboard del administrador | Funcional (datos de ejemplo) |
| `/admin/ordenes`, `/clientes`, `/vehiculos`, `/inventario`, `/distribuidores` | Secciones | Placeholder "Próximamente" |
| `/client`, `/mechanic` | Portales | Placeholder "Próximamente" |

Nota: el login realiza la llamada real a `POST /auth/login` del backend
(pendiente de desplegar los microservicios). Si el backend no está disponible,
se muestra el error de credenciales.

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