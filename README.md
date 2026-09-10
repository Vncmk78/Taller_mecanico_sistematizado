# Taller Mecánico — Sistema de Gestión

Proyecto de Taller de Integración II — Universidad Católica de Temuco (UCT).

Digitalizamos la gestión integral de talleres mecánicos: conectamos la
eficiencia operativa del administrador con la transparencia y trazabilidad que
exige el cliente.

## Estructura del Repositorio

| Carpeta | Descripción |
| --- | --- |
| `frontend/` | Aplicación web (React + Vite + TypeScript) |
| `Requerimientos.md` | Documento de requerimientos funcionales y no funcionales |

## Roles del Sistema

- **Cliente:** agenda horas, sigue sus órdenes, revisa evidencia del diagnóstico
  y aprueba presupuestos.
- **Mecánico:** gestiona órdenes, sube evidencia visual y registra repuestos.
- **Administrador:** supervisa vehículos, clientes, órdenes, inventario y
  distribuidores.

## Estado Actual

Escrito por **Gustavo** (rama `Gustavo`). Implementado:
- Landing / vista de inicio.
- Inicio de sesión con validación (React Hook Form + Zod).
- Panel de administrador (layout con sidebar y dashboard).
- Estructura con arquitectura hexagonal (dominio, aplicación, infraestructura).

Pendiente: conexión con el backend, portales de cliente y mecánico, guardas de
rutas por rol y pruebas automatizadas.

## Para ejecutar el frontend localmente

Ver [`frontend/README.md`](frontend/README.md#c%C3%B3mo-ejecutar-el-proyecto-localmente).
