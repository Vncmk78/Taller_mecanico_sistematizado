# Taller Mecánico — Sistema de Gestión

Proyecto de Taller de Integración II — Universidad Católica de Temuco (UCT).

Digitalizamos la gestión integral de talleres mecánicos: conectamos la
eficiencia operativa del administrador con la transparencia y trazabilidad que
exige el cliente.

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
