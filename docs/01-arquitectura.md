# 01 — Arquitectura

## 1. Vista general

```
                         Internet
                            │
        ┌───────────────────┴────────────────────┐
        │                                        │
        ▼                                        ▼
┌──────────────────┐                   ┌──────────────────────┐
│  Web (React)     │                   │  App móvil           │
│  tallerconnect…  │                   │  (consume la API)    │
└────────┬─────────┘                   └──────────┬───────────┘
         │ /api/* (proxy Nginx)                   │ HTTPS
         └───────────────────┬────────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │  Gateway (FastAPI)  │  api-tallerconnect.inf.uct.cl
                  │  /api/*             │
                  └──────────┬──────────┘
                             │ HTTP interno (Service :80)
        ┌──────────┬─────────┼──────────┬───────────┐
        ▼          ▼         ▼          ▼           │
     ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
     │ MS1  │  │ MS2  │  │ MS3  │  │ MS4  │        │
     │ auth │  │orden │  │presu │  │evid. │        │
     └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘        │
        │         │         │         │            │
     ┌──▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐        │
     │ PG1  │  │ PG2  │  │ PG3  │  │ PG4  │        │
     └──────┘  └──────┘  └──────┘  └──┬───┘        │
                                      │ S3        │
                                   ┌──▼─────┐     │
                                   │ MinIO  │◄────┘
                                   └────────┘
```

Cada microservicio tiene **su propia base PostgreSQL** y **no comparte tablas**
con los demás. Las referencias entre servicios son lógicas (por ejemplo, un
`orden_id`) y se validan por HTTP con el JWT del usuario o con un secreto de
servicio.

## 2. Componentes desplegados

| Componente | App en Kubero | Imagen | Proceso | Base |
| --- | --- | --- | --- | --- |
| Gateway | `gateway` | `tallerconnect-backend` | `SGTM_SERVICIO=gateway` | — |
| Autenticación y usuarios | `ms1` | `tallerconnect-backend` | `SGTM_SERVICIO=ms1` | PostgreSQL `ms1-postgres` |
| Vehículos y órdenes | `ms2` | `tallerconnect-backend` | `SGTM_SERVICIO=ms2` | PostgreSQL `ms2-postgres` |
| Presupuestos e inventario | `ms3` | `tallerconnect-backend` | `SGTM_SERVICIO=ms3` | PostgreSQL `ms3-postgres` |
| Evidencia multimedia | `ms4` | `tallerconnect-backend` | `SGTM_SERVICIO=ms4` | PostgreSQL `ms4-postgres` |
| Web | `web` | `tallerconnect-frontend` | Nginx :80 | — |
| Almacenamiento de objetos | `minio` | `elestio/minio:latest` | MinIO :9000 | volumen `minio-data-cephfs` |

Las cinco apps backend usan **la misma imagen**: `SGTM_SERVICIO` decide qué
módulo arranca. Esto evita mantener cinco imágenes distintas y garantiza que
todas las versiones del backend sean idénticas.

## 3. Responsabilidades de cada servicio

### Gateway (`backend/gateway`)

- Única puerta de entrada de negocio: expone `/api/*`.
- Enruta por **prefijo de ruta** al microservicio correspondiente.
- Aplica CORS (solo el dominio web), límites de tamaño de cuerpo, timeouts por
  fase y reintentos controlados.
- Agrega `X-Request-ID` a las respuestas para trazabilidad.
- Expone `/api/health` y `/api/health/servicios`.

Prefijos y destinos (definidos en `backend/gateway/rutas.py`):

| Prefijo | Microservicio |
| --- | --- |
| `auth`, `notificaciones` | MS1 |
| `vehiculos`, `ordenes`, `clientes` | MS2 |
| `presupuestos`, `repuestos`, `proveedores`, `inventario` | MS3 |
| `evidencias` | MS4 |

### MS1 — Autenticación y usuarios (`backend/services/ms1_auth`)

- Registro, login, JWT, `/me`.
- Usuarios y roles (`cliente`, `mecanico`, `administrador`).
- Notificaciones internas: recibe eventos de MS2 y MS3, los persiste y expone la
  bandeja del usuario.
- Registro de dispositivos push (FCM).
- Cola de entregas por canal (correo / push).

### MS2 — Vehículos y órdenes (`backend/services/ms2_taller`)

- Vehículos por cliente.
- Órdenes de trabajo, historial de estados, bitácora, capacidad diaria y por
  mecánico.
- Entrega, devolución, cancelaciones y solicitudes de nueva atención.
- Publica eventos de cambio de estado hacia MS1 (worker de outbox).

### MS3 — Presupuestos, repuestos y proveedores (`backend/services/ms3_presupuestos`)

- Presupuestos versionados, envío y decisión del cliente.
- Proveedores, repuestos, stock, umbrales, alertas y trazabilidad.
- Reserva, consumo y liberación de repuestos por orden.
- Publica avisos de presupuesto y de stock hacia MS1 (worker de outbox).

### MS4 — Evidencia multimedia (`backend/services/ms4_evidencias`)

- Subida de fotos y videos a MinIO/S3 (multipart, hasta 12 MiB por petición en la
  Gateway; 10 MiB foto y 100 MiB video en el servicio).
- Metadatos en PostgreSQL y archivo en el bucket `evidencias`.
- Reglas de visibilidad para el cliente.
- URLs de descarga prefirmadas con vigencia limitada.

### Web (`frontend/`)

- React + Vite + TypeScript.
- Nginx sirve el build y hace proxy de `/api/*` a `GATEWAY_UPSTREAM`.
- El build fija `VITE_API_URL=/api`, por lo que la web siempre llama a su mismo
  origen y no necesita CORS para sí misma.

## 4. Comunicación entre servicios

| Origen → destino | Para qué | Cómo se autentica |
| --- | --- | --- |
| Web → Gateway | Todo el negocio | JWT del usuario |
| App móvil → Gateway | Todo el negocio | JWT del usuario |
| Gateway → MS1..MS4 | Enrutar la petición | JWT del usuario (se reenvía) |
| MS2 → MS3 | Verificar disponibilidad/reserva de repuestos | JWT del usuario |
| MS3 → MS2 | Verificar que una orden es visible para el usuario | JWT del usuario |
| MS4 → MS2 | Verificar que la orden es visible para el usuario | JWT del usuario |
| MS4 → MS3 | Verificar que el presupuesto pertenece a la orden | JWT del usuario |
| MS1 → MS2 | Resolver el destinatario de un aviso | `X-Service-Token` |
| MS2 → MS1 | Publicar eventos de orden | `X-Service-Token` |
| MS3 → MS1 | Publicar avisos de presupuesto/stock | `X-Service-Token` |
| MS4 → MinIO | Guardar/leer archivos | Access key + secret (S3v4) |

Los **secretos de servicio** son independientes del JWT:

- `EVENT_SHARED_SECRET` (MS1 ↔ MS2) para eventos de orden.
- `MS3_EVENT_SHARED_SECRET` (MS1 ↔ MS3) para avisos de presupuesto y stock.
- `MS2_NOTIFICATION_LOOKUP_SECRET` (MS1 → MS2) para resolver destinatarios.

## 5. Estados de una orden

Códigos oficiales (`backend/services/ms2_taller/models/estado_orden.py`):

| Código | Estado | Terminal |
| --- | --- | --- |
| 1 | Recibido | No |
| 2 | Esperando diagnóstico | No |
| 3 | Esperando aprobación de presupuesto | No |
| 4 | Esperando repuestos | No |
| 5 | En reparación | No |
| 6 | Listo | No |
| 7 | Entregado | **Sí** |
| 8 | Cancelado | **Sí** |

Transiciones permitidas (`backend/services/ms2_taller/domain/transiciones_orden.py`):

| Desde | Evento | Hacia | Operación que lo dispara |
| --- | --- | --- | --- |
| — | creación | 1 | `POST /api/ordenes` |
| 1 | primera asignación | 2 | `PUT /api/ordenes/{id}/mecanico` |
| 2 | envío primer presupuesto | 3 | `POST /api/presupuestos/{id}/versiones/{n}/envio` |
| 3 | aprobación con repuestos disponibles | 5 | `POST /api/presupuestos/{id}/versiones/{n}/decision` |
| 3 | aprobación con repuestos faltantes | 4 | `POST /api/presupuestos/{id}/versiones/{n}/decision` |
| 4 | disponibilidad de repuestos | 5 | `POST /api/inventario/ordenes/{id}/reserva` + confirmación |
| 5 | finalización del trabajo | 6 | `PATCH /api/ordenes/{id}/estado` (mecánico) |
| 6 | entrega física | 7 | `POST /api/ordenes/{id}/entrega` (administrador) |
| 3 | rechazo del primer presupuesto | 8 | `POST /api/presupuestos/{id}/versiones/{n}/decision` |
| 1, 2, 3 | cancelación solicitada y confirmada | 8 | `POST /api/ordenes/{id}/cancelacion` + `.../cancelacion/confirmacion` |

Reglas importantes:

- Una orden en estado **terminal** (7 u 8) no admite más transiciones.
- El `PATCH /api/ordenes/{id}/estado` genérico **solo** permite `5 → 6` y solo
  al mecánico asignado. Las demás transiciones tienen su operación específica.
- La cancelación genérica no puede aplicarse si ya existe una **aprobación
  inicial** de presupuesto: en ese caso se responde `409`.
- Un presupuesto rechazado por el cliente cancela la orden (`3 → 8`) y libera la
  reserva de repuestos.

## 6. Notificaciones

MS2 y MS3 escriben eventos en una **outbox** dentro de su propia base. Un worker
en segundo plano los publica a MS1, que los persiste como notificaciones de los
usuarios y encola las entregas por canal.

| Evento | Origen | Destinatario |
| --- | --- | --- |
| `orden.estado_cambiado` | MS2 | cliente dueño de la orden |
| `nueva_atencion.solicitada` | MS2 | todos los administradores |
| `nueva_atencion.revisada` | MS2 | cliente solicitante |
| `presupuesto.enviado` | MS3 | cliente dueño de la orden |
| `presupuesto.decidido` | MS3 | todos los administradores |
| `stock.alerta` | MS3 | todos los administradores |

Canales de entrega:

- **En la app/web:** siempre disponible (bandeja `GET /api/notificaciones`).
- **Push (FCM):** requiere que el dispositivo esté registrado. Sin proyecto FCM
  configurado, la entrega queda como `sin_dispositivo` o `pendiente`.
- **Correo (SMTP):** **desactivado** en este despliegue porque no hay cuenta
  SMTP disponible. Las notificaciones dentro de la aplicación funcionan igual.

## 7. Decisiones de diseño del despliegue

| Decisión | Motivo |
| --- | --- |
| Una sola imagen backend para 5 apps | Menos mantenimiento y versiones consistentes |
| Una base PostgreSQL por microservicio | Aislamiento de datos, igual que el diseño original |
| Imágenes públicas en GHCR | Kubero UCT **no construye** imágenes; solo despliega |
| Dominios `msN-tallerconnect` | Permiten health checks y depuración directa |
| `ms4-tallerconnect` reutilizado para MinIO | No había DNS nuevo disponible en la UCT |
| MS4 con dominio `ms4-interno-tallerconnect` | El dominio anterior quedó para MinIO |
| Usuario MinIO limitado (`ms4-evidencias`) | MS4 no necesita root; solo el bucket `evidencias` |
| URLs internas sin puerto | El Service de Kubero escucha en 80 y apunta a `http` |
| Workflow solo en `kubero-deploy` | Evita publicar imágenes desde `main` mientras se estabiliza |

## 8. Versiones y artefactos

| Artefacto | Valor |
| --- | --- |
| Repositorio | <https://github.com/Vncmk78/Taller_mecanico_sistematizado> |
| Rama de despliegue | `kubero-deploy` |
| Commit de código desplegado | `18d02b9` (`main`) |
| Commit del workflow | `c855bab` |
| Imagen backend | `ghcr.io/vncmk78/tallerconnect-backend:latest` · `:sha-c855bab` |
| Imagen frontend | `ghcr.io/vncmk78/tallerconnect-frontend:latest` · `:sha-c855bab` |
| Build | GitHub Actions run `43548759119` (conclusión: success) |

> Las imágenes llevan dos etiquetas: `latest` y `sha-<commit>`. Para producción se
> recomienda fijar `sha-<commit>` y no depender de `latest`.
