# Documento de Requerimientos — Sistema de Gestión de Talleres Mecánicos

**Proyecto:** Taller de Integración II — Universidad Católica de Temuco (UCT)
**Grupo:** 10
**Fecha:** Septiembre 2026

---

## 1. Objetivo del Sistema

Digitalizar la gestión integral de talleres mecánicos, conectando la eficiencia
operativa del administrador con la transparencia que requiere el cliente. Cada
vehículo mantiene un historial de mantenciones trazable, con evidencia visual
(fotos/videos) y control estricto de estados de cada orden de trabajo.

## 2. Roles del Sistema

| Rol | Descripción |
| --- | --- |
| **Cliente** | Solicita hora, sigue sus órdenes, revisa evidencia visual y aprueba o rechaza presupuestos |
| **Mecánico** | Gestiona órdenes, sube diagnósticos con evidencia y registra repuestos usados |
| **Administrador** | Supervisa el taller completo: vehículos, clientes, inventario y distribuidores |

## 3. Requerimientos Funcionales

### 3.1 Autenticación y Usuarios
- **RF-01:** El sistema debe permitir iniciar sesión con correo electrónico y contraseña.
- **RF-02:** La sesión debe persistir mediante token JWT (guardado en el navegador).
- **RF-03:** El sistema debe redirigir al usuario a su portal según su rol
  (`cliente`, `mecanico`, `administrador`).
- **RF-04:** El usuario debe poder cerrar sesión.
- **RF-05:** Si el token es inválido o expira (respuesta 401), el sistema debe
  limpiar la sesión y redirigir al login.

### 3.2 Vehículos
- **RF-06:** El sistema debe permitir registrar, consultar, editar y eliminar vehículos.
- **RF-07:** Cada vehículo se identifica por su patente y guarda marca, modelo,
  año y kilometraje.
- **RF-08:** El sistema debe poder buscar un vehículo por patente y mostrar su
  historial completo de órdenes.

### 3.3 Órdenes de Trabajo
- **RF-09:** El sistema debe permitir crear una orden de trabajo asociada a un
  vehículo y a un mecánico asignado.
- **RF-10:** Cada orden debe avanzar por estados controlados:

  `recibido → esperando_diagnostico → esperando_aprobacion → esperando_repuestos → en_reparacion → listo → entregado`

  Además de un estado `cancelado`.
- **RF-11:** El mecánico debe poder subir fotos y videos del diagnóstico como
  evidencia de la cotización.
- **RF-12:** El cliente debe poder revisar la evidencia y aprobar o rechazar el
  presupuesto.

### 3.4 Inventario y Distribuidores
- **RF-13:** El administrador debe poder gestionar el inventario de repuestos.
- **RF-14:** El sistema debe alertar cuando el stock de un repuesto esté bajo.
- **RF-15:** El sistema debe registrar distribuidores (oficiales o genéricos)
  para la trazabilidad del origen de cada repuesto instalado.

### 3.5 Panel de Administrador
- **RF-16:** El panel debe mostrar un resumen operativo: vehículos en taller,
  esperando diagnóstico, listos para entrega y presupuestos por revisar.
- **RF-17:** El panel debe mostrar la cola de trabajo activa con el estado de
  cada orden.
- **RF-18:** El panel debe permitir acceder a la gestión de órdenes, clientes,
  vehículos, inventario y distribuidores.

## 4. Requerimientos No Funcionales

### 4.1 Arquitectura
- **RNF-01:** El frontend debe seguir **arquitectura hexagonal**, separando
  dominio (`domain/`), aplicación (`application/`) e infraestructura
  (`infrastructure/`).
- **RNF-02:** La comunicación con el backend debe realizarse a través de una
  capa de servicios HTTP desacoplada (puertos e implementaciones).

### 4.2 Calidad de Código
- **RNF-03:** Se deben aplicar los principios **SOLID** en el diseño de clases
  y responsabilidades.
- **RNF-04:** Las entidades y contratos deben estar tipados con TypeScript.
- **RNF-05:** El código debe ejecutar correctamente las tareas de lint y build:
  `npm run lint` y `npm run build`.

### 4.3 Seguridad
- **RNF-06:** Las contraseñas no deben almacenarse en texto plano en el
  navegador ni en los logs.
- **RNF-07:** El token JWT debe enviarse en el encabezado `Authorization: Bearer <token>`.

### 4.4 Edición del Proyecto
- **RNF-08:** Los archivos de *skills* de asistencia de desarrollo
  (`frontend/src/skills/`) son internos del flujo de trabajo y **no** forman
  parte del repositorio público (ignorados por git).

## 5. Stack Tecnológico (Frontend)

| Tecnología | Uso |
| --- | --- |
| React 19 + Vite | Base del frontend |
| TypeScript | Tipado estático |
| React Router | Navegación entre portales y secciones |
| Tailwind CSS v4 | Estilos y tema (dark glassmorphism) |
| Axios | Cliente HTTP con interceptores de JWT |
| TanStack Query | Cache y sincronización de datos con la API |
| Zustand | Estado global (autenticación) |
| React Hook Form + Zod | Formularios y validación |
| Lucide React | Iconos |

## 6. Alcance Actual (Septiembre 2026)

Implementado y funcional:
- Estructura del proyecto React con arquitectura hexagonal.
- Vista de inicio (landing) con diseño basado en el prototipo.
- Vista de inicio de sesión con validación y manejo de error.
- Panel de administrador (layout con sidebar, dashboard de ejemplo).

Pendiente (próximas iteraciones):
- Conexión real con los microservicios del backend (login, CRUD de vehículos y órdenes).
- Portales de Cliente y Mecánico.
- Guardas de rutas por rol.
- Pruebas unitarias (Vitest) y E2E (Playwright).