# TallerConnect — Documentación del despliegue en Kubero UCT

Esta carpeta reúne la documentación operativa y técnica del sistema **TallerConnect**
tal como quedó desplegado y verificado en el clúster **Kubero de la Universidad
Católica de Temuco (UCT)**.

> **Fecha de la verificación:** 15 de noviembre de 2026
> **Versión desplegada en esa verificación:** imágenes `sha-c855bab` del commit
> `18d02b9`. El flujo vigente es `Vicente → Develop → main`: el workflow de
> imágenes está en `main` y publica solo con `push` a `main`; `kubero-deploy`
> se conserva pero ya no dispara builds.
> **Estado:** los 7 componentes (Gateway, MS1–MS4, web y MinIO) están levantados y
> respondiendo. Los flujos funcionales principales fueron probados de punta a punta
> contra el ambiente real.

---

## Índice

| Documento | Para quién | Qué contiene |
| --- | --- | --- |
| [01 — Arquitectura](01-arquitectura.md) | Todo el equipo | Componentes, comunicación entre servicios, imágenes, decisiones de diseño |
| [02 — Despliegue en Kubero](02-despliegue-kubero.md) | Quien administra la infraestructura | Cómo está montado el pipeline, apps, addons, dominios y almacenamiento; cómo replicarlo |
| [03 — Variables de entorno](03-variables-entorno.md) | Backend / infraestructura | Todas las variables por aplicación, con valores no secretos y ubicación de los secretos |
| [04 — Datos de prueba](04-datos-de-prueba.md) | QA / equipo móvil | Cuentas, vehículos, órdenes, presupuestos e inventario de demostración |
| [05 — API para la app móvil](05-api-app-movil.md) | **Equipo de app móvil** | URL base, autenticación, catálogo de endpoints, ejemplos reales, errores, push |
| [06 — Runbook de operación](06-runbook-operacion.md) | Infraestructura / soporte | Reiniciar, ver logs, actualizar versión, migrar, respaldar y resolver problemas |
| [07 — Pruebas realizadas](07-pruebas-realizadas.md) | Todo el equipo / evaluación | Matriz de verificaciones con resultados reales |
| [08 — Pendientes y deuda técnica](08-pendientes-y-deuda.md) | Todo el equipo | Limitaciones conocidas, decisiones tomadas y próximos pasos |
| [09 — Health checks](09-health-checks.md) | Infraestructura / evaluación | Health checks de contenedores y servicios, script de verificación y evidencia |

---

## Accesos rápidos

| Recurso | URL | Estado |
| --- | --- | --- |
| Aplicación web | <https://tallerconnect.inf.uct.cl> | 200 |
| API Gateway (para la app móvil) | <https://api-tallerconnect.inf.uct.cl> | 200 |
| Salud de la Gateway | <https://api-tallerconnect.inf.uct.cl/api/health> | 200 |
| Swagger / OpenAPI | <https://api-tallerconnect.inf.uct.cl/docs> · <https://api-tallerconnect.inf.uct.cl/openapi.json> | 200 |
| Panel de Kubero | <https://kubero.inf.uct.cl> | — (credenciales del responsable) |
| Consola de MinIO | <https://ms4-tallerconnect.inf.uct.cl:36553> | — (credenciales del responsable) |

Los microservicios también tienen dominio público, pero **no deben usarse desde
fuera**: todo el tráfico de negocio entra por la Gateway (`/api/*`). Ver
[02 — Despliegue](02-despliegue-kubero.md#5-dominios).

---

## Regla de seguridad importante

**Este repositorio de GitHub es público.** Por eso:

- La documentación **no contiene** el JWT compartido, las contraseñas de
  PostgreSQL, las claves de MinIO ni los secretos de eventos.
- Esos valores están únicamente en el **panel de Kubero** (variables de cada app)
  y se solicitan al responsable del proyecto.
- Las contraseñas que sí aparecen aquí son de **cuentas de demostración** creadas
  para pruebas; no dan acceso a infraestructura.
- Nunca agregues un `.env`, un volcado de base de datos ni capturas del panel con
  secretos visibles a un commit.

---

## Resumen del sistema

TallerConnect digitaliza la gestión de un taller mecánico con tres roles:

- **Cliente:** registra sus vehículos, sigue sus órdenes, revisa evidencias y
  aprueba o rechaza presupuestos.
- **Mecánico:** atiende las órdenes asignadas, registra bitácora, consume
  repuestos y sube evidencia.
- **Administrador:** supervisa vehículos, órdenes, capacidad, inventario,
  proveedores y notificaciones.

La arquitectura se mantiene igual que en el diseño original: **una web React**,
**una Gateway FastAPI** y **cuatro microservicios FastAPI** con base de datos
independiente cada uno, más **MinIO** para las evidencias. Lo que cambió es la
plataforma: **Kubero UCT reemplaza a Vercel** y **PostgreSQL de Kubero reemplaza a
Neon**. Los despliegues anteriores en Vercel/Neon **no se borraron ni modificaron**;
simplemente dejan de ser el ambiente vigente.

---

## Cómo leer esta documentación

- Si vas a **consumir la API** (app móvil, integraciones): empieza por
  [05 — API para la app móvil](05-api-app-movil.md) y usa las cuentas de
  [04 — Datos de prueba](04-datos-de-prueba.md).
- Si vas a **operar o redeployar**: lee
  [02 — Despliegue en Kubero](02-despliegue-kubero.md),
  [03 — Variables](03-variables-entorno.md) y
  [06 — Runbook](06-runbook-operacion.md).
- Si necesitas **contexto de diseño o defender el proyecto**: revisa
  [01 — Arquitectura](01-arquitectura.md) y
  [07 — Pruebas](07-pruebas-realizadas.md).

---

## Responsables

| Rol | Nombre | Contacto |
| --- | --- | --- |
| Responsable del despliegue / panel Kubero | _(completar)_ | _(completar)_ |
| Backend / Gateway | _(completar)_ | _(completar)_ |
| Frontend web | _(completar)_ | _(completar)_ |
| App móvil | _(completar)_ | _(completar)_ |

> Completar esta tabla antes de entregar el proyecto.
