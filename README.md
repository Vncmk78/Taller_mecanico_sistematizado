# Taller Mecánico — Sistema de Gestión

Proyecto de Taller de Integración II — Universidad Católica de Temuco (UCT).

Digitalizamos la gestión integral de talleres mecánicos: conectamos la
eficiencia operativa del administrador con la transparencia y trazabilidad que
exige el cliente.

## Documentación del despliegue vigente

El ambiente actual está desplegado en el **clúster Kubero de la UCT**. Kubero
reemplaza a Vercel y el PostgreSQL de Kubero reemplaza a Neon; los despliegues
anteriores se conservan intactos, pero ya no son el ambiente vigente.

Toda la documentación operativa y de integración está en [`docs/`](docs/README.md):

| Documento | Para quién |
| --- | --- |
| [Índice y accesos](docs/README.md) | Todo el equipo |
| [01 — Arquitectura](docs/01-arquitectura.md) | Todo el equipo |
| [02 — Despliegue en Kubero](docs/02-despliegue-kubero.md) | Infraestructura |
| [03 — Variables de entorno](docs/03-variables-entorno.md) | Backend / infraestructura |
| [04 — Datos de prueba](docs/04-datos-de-prueba.md) | QA / app móvil |
| [05 — API para la app móvil](docs/05-api-app-movil.md) | **Equipo de app móvil** |
| [06 — Runbook de operación](docs/06-runbook-operacion.md) | Infraestructura / soporte |
| [07 — Pruebas realizadas](docs/07-pruebas-realizadas.md) | Todo el equipo |
| [08 — Pendientes y deuda](docs/08-pendientes-y-deuda.md) | Todo el equipo |

> El repositorio es **público**: los secretos no están aquí. Se administran en el
> panel de Kubero. Ver la regla de seguridad en [`docs/README.md`](docs/README.md#regla-de-seguridad-importante).

## Estructura del Repositorio

| Carpeta | Descripción |
| --- | --- |
| `frontend/` | Aplicación web (React + Vite + TypeScript) |
| `backend/gateway/` | API Gateway FastAPI; entrada de la web y la aplicación móvil por `/api/*` |
| `backend/services/` | Cuatro microservicios FastAPI con bases PostgreSQL independientes |
| `backend/shared/` | Autenticación, configuración y utilidades compartidas |
| `backend/tests/` | Pruebas automatizadas del backend y de la Gateway |
| `Requerimientos.md` | Documento de requerimientos funcionales y no funcionales |

## Roles del Sistema

- **Cliente:** agenda horas, sigue sus órdenes, revisa evidencia del diagnóstico
  y aprueba presupuestos.
- **Mecánico:** gestiona órdenes, sube evidencia visual y registra repuestos.
- **Administrador:** supervisa vehículos, clientes, órdenes, inventario y
  distribuidores.

## Estado Actual

La implementación vigente utiliza el frontend de `frontend/`, la Gateway y los
cuatro servicios de `backend/services/`: autenticación y usuarios; vehículos y
órdenes; presupuestos e inventario; evidencia multimedia. El frontend consume la
Gateway y cuenta con rutas por rol y pruebas Vitest. El backend se verifica con
pytest.

El ambiente publicado corre en Kubero UCT con imágenes de GHCR, PostgreSQL por
servicio y MinIO para las evidencias. Los pasos, variables y verificaciones están
en [`docs/`](docs/README.md).

El [mapa de rutas](frontend/docs/mapa-de-rutas.md) y los
[contratos API](backend/docs/contratos-api-gateway.md) describen las operaciones
y los límites de cada flujo. La disponibilidad del ambiente publicado se debe
comprobar por separado.

El backend Node, su suite Jest de la raíz y el MS1 alternativo `auth-service/`
se retiraron por no formar parte de esta implementación. Los ejemplos de esos
sistemas que permanecen en documentos son registros históricos.

`backend/_legacy_monolito_20260907/` y `presupuestos-service/` conservan versiones
anteriores con sus propias migraciones. No son los servicios configurados en
`vercel.json`; se mantienen pendientes de revisión antes de retirar esos
historiales.

## Para ejecutar el frontend localmente

Ver [`frontend/README.md`](frontend/README.md#c%C3%B3mo-ejecutar-el-proyecto-localmente).

Para el backend, ver [`backend/README.md`](backend/README.md). Los comandos npm
se ejecutan desde `frontend/`; ya no existe un paquete Node en la raíz.
