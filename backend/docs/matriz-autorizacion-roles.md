# Matriz de autorización por roles — SGTM

Documento de referencia que responde **qué puede hacer cada rol en cada recurso**
del sistema. Cubre los cuatro microservicios y distingue entre lo que ya está
implementado y verificado y lo que solo tiene regla definida pero **sin endpoint**.

No reemplaza al contrato de la API: las rutas, cuerpos y errores están en
[`contratos-api-gateway.md`](contratos-api-gateway.md). Este documento define
**quién** puede consumir cada una. Ante cualquier duda sobre una firma o un status
code, manda el contrato; ante cualquier duda sobre **quién** puede ver o hacer
algo, manda esta matriz.

## 1. Alcance

| Servicio | Puerto | Recurso | Estado |
|---|---|---|---|
| Gateway | 8000 | Enrutado `/api/*` | Enrutado, **no autoriza** |
| MS1 | 8001 | Autenticación y usuarios | Endpoints de negocio implementados |
| MS2 | 8002 | Vehículos y órdenes de trabajo | Endpoints implementados |
| MS3 | 8003 | Presupuestos, repuestos, proveedores, inventario | Endpoints iniciales de `/presupuestos` |
| MS4 | 8004 | Evidencias multimedia | Endpoints de recepción y consulta implementados; la visibilidad se valida contra MS2 |

La Gateway **no valida el JWT**: se limita a reenviar la petición. Toda decisión de
autorización ocurre en el microservicio que atiende la ruta.

## 2. Fuentes de verdad

| Fuente | Qué define |
|---|---|
| `backend/shared/auth.py` | Los tres roles, la emisión del token y su validación. **Contrato único**: no reimplementar la validación del JWT en ningún servicio |
| `backend/shared/auth.py` → `NombreRol` | `cliente`, `mecanico`, `administrador`. No existe `role` en singular |
| `services/ms2_taller/services/ordenes.py` → `_filtro_visibilidad` | La visibilidad de órdenes por rol, con soporte multirol |
| `services/ms2_taller/dependencies.py` → `resolver_cliente_actual` | El guard de vehículos: exige rol Cliente y perfil local |
| `services/ms3_presupuestos/dependencies.py` → `requerir_roles` | Guard de "al menos uno de estos roles"; lo usa `routers/presupuestos.py` (Mecánico o Administrador) |
| `services/ms4_evidencias/dependencies.py` → `obtener_principal_actual` / `obtener_token_bearer` | Validan el token en MS4; el segundo reenvía el JWT a MS2 para validar la orden (§4.5) |
| [`modelo-evidencias.md`](modelo-evidencias.md) §Reglas de visibilidad | La visibilidad de evidencias por rol, en detalle |
| [`maquina-estados-ordenes.md`](maquina-estados-ordenes.md) | Los ocho estados y sus transiciones |

> La sección 6 de `TAREA_6_FLUJO_AUTENTICACION.md` contiene una tabla de permisos
> heredada del monolito Node (`/orders/me`, `PATCH /orders/:id`, `GET /users`,
> claim `role` singular, `id="usr_222"`). Describe endpoints que **no existen** y un
> contrato de token incompatible. Está **superada por este documento**.

## 3. Los tres roles

| Rol | Valor en el claim `roles` | Qué es |
|---|---|---|
| Cliente | `cliente` | Persona que trae su vehículo y consulta sus órdenes |
| Mecánico | `mecanico` | Profesional que atiende las órdenes que le asignan |
| Administrador | `administrador` | Personal del taller que crea órdenes y asigna responsables |

Un usuario puede tener **más de un rol a la vez**. El registro público asigna
siempre el rol `cliente` en el servidor; el body de registro **no acepta** `role`
(`extra="forbid"` → `422`).

### 3.1 Regla multirol

Los roles **se acumulan**: un usuario Administrador+Mecánico tiene ambos alcances.
La forma concreta está en `_filtro_visibilidad`
(`services/ms2_taller/services/ordenes.py`):

| Situación | Resultado |
|---|---|
| Incluye `administrador` | Acceso **global**, sin filtro |
| Incluye `cliente` **y** `mecanico` | **Unión** de ambos alcances, sin duplicados |
| No incluye ninguno de los tres | `false()` — no ve nada |

Nunca se debe intersectar alcances: un usuario con dos roles **no** debe ver menos
que uno que tenga solo uno de ellos.

## 4. Matriz maestra

Leyenda: ✅ permitido · ⚠️ permitido con condición · ❌ prohibido (`403`) ·
— sin endpoint, no consumible · 📐 regla definida, pendiente de implementación

### 4.1 Identidad (MS1)

| Capacidad | Cliente | Mecánico | Administrador |
|---|---|---|---|
| `POST /api/auth/register` | público | público | público |
| `POST /api/auth/login` | público | público | público |
| `GET /api/auth/me` | ✅ el propio | ✅ el propio | ✅ el propio |
| Ver datos de **otros** usuarios | — | — | — |
| Asignar roles | — | — | — |

No existe ningún endpoint de administración de usuarios.

### 4.2 Vehículos (MS2)

Todos los endpoints pasan por `resolver_cliente_actual`, que exige rol `cliente` y
perfil local; sin perfil local responde `404`, no `403`.

| Capacidad | Cliente | Mecánico | Administrador |
|---|---|---|---|
| `POST /api/vehiculos` | ✅ | ❌ | ⚠️ * |
| `GET /api/vehiculos` | ✅ los suyos | ❌ | ⚠️ * |
| `GET /api/vehiculos/{id}` | ✅ el suyo | ❌ | ⚠️ * |
| `PATCH /api/vehiculos/{id}` | ✅ el suyo | ❌ | ⚠️ * |
| `GET /api/vehiculos/asignados` | — | — | — |

\* Solo si la cuenta **además** tiene el rol `cliente` y existe su perfil `Cliente`
en MS2. El rol `administrador` por sí solo **no** da acceso a vehículos.

El mecánico **no tiene hoy ninguna forma de listar los vehículos que atiende**: esa
ruta no existe.

### 4.3 Órdenes de trabajo (MS2)

| Capacidad | Cliente | Mecánico | Administrador |
|---|---|---|---|
| `POST /api/ordenes` | ❌ | ❌ | ✅ |
| `GET /api/ordenes` | ⚠️ de sus vehículos | ⚠️ asignadas | ✅ todas |
| `GET /api/ordenes/{id}` | ⚠️ de sus vehículos | ⚠️ asignada | ✅ cualquiera |
| `PUT /api/ordenes/{id}/mecanico` | ❌ | ❌ | ✅ |
| `GET /api/ordenes/{id}/historial` | — | — | — |
| Cambio general de estado | — | — | — |

Detalles que condicionan la matriz:

- **Crear** una orden es exclusivo del Administrador (`routers/ordenes.py:50`).
- **Visibilidad**: el alcance del Cliente son las órdenes de los vehículos de su
  perfil; el del Mecánico son las órdenes con `mecanico_actual_id` igual a su
  usuario. Un Cliente o un Mecánico que consulta una orden fuera de su alcance
  recibe `404`, **no** `403`, para no revelar la existencia de recursos ajenos.
- **Asignar o reasignar** es exclusivo del Administrador
  (`routers/ordenes.py:150`). Un Administrador que además es Mecánico **no puede
  autoasignarse**: responde `409`.
- La asignación es **idempotente** si se repite el mismo `mecanico_id`. En la
  primera asignación de una orden `Recibido` la orden pasa a
  `Esperando diagnóstico` y quedan registrados `HistorialAsignacion` e
  `HistorialEstado` en la misma transacción. `Entregado` y `Cancelado` rechazan
  asignaciones con `409`.
- `mecanico_id` es hoy una **referencia lógica** a MS1: **no** se valida en el
  servidor que exista, esté activo ni tenga el rol `mecanico`, ni se aplica un
  máximo de órdenes activas.

### 4.4 Presupuestos, repuestos, proveedores e inventario (MS3)

| Capacidad | Cliente | Mecánico | Administrador |
|---|---|---|---|
| Crear presupuesto de una orden (`POST /presupuestos`, versión 1 en borrador) | ❌ 403 | ✅ | ✅ |
| Listar / buscar por orden (`GET /presupuestos?orden_id=`) | ✅ solo su orden y con `orden_id` | ✅ | ✅ |
| Detalle y versión (`GET /presupuestos/{id}`, `/versiones/{n}`) | ✅ solo sus órdenes, sin borradores | ✅ | ✅ |
| Crear la versión siguiente (`POST /presupuestos/{id}/versiones`) | ❌ 403 | ✅ | ✅ |
| Reemplazar ítems de una versión en borrador (`PUT .../versiones/{n}/items`) | ❌ 403 | ✅ | ✅ |
| Enviar la versión al cliente (`POST .../versiones/{n}/envio`) | ❌ 403 | ❌ 403 | ✅ |
| Aprobar o rechazar (`POST .../versiones/{n}/decision`) | ✅ solo dueño | ❌ 403 | ❌ 403 |
| Repuestos, proveedores, inventario | — | — | — |

- Guards en `services/ms3_presupuestos/routers/presupuestos.py` (`requerir_roles`).
- **Propiedad del cliente:** MS3 no conoce al dueño del vehículo (§8). Llama a
  `GET {MS3_MS2_URL}/ordenes/{orden_id}` con el JWT del cliente: si MS2 no se la
  muestra, MS3 responde `404` (sin revelar si el presupuesto existe); si MS2 no
  responde, `503`. Implementación: `services/ms3_presupuestos/integracion_ms2.py`.
- El cliente no ve versiones en borrador: para él no existen (`404`).
- Pendiente: limitar al mecánico a las órdenes que tiene asignadas (dato de MS2).
- Una versión enviada o aprobada no se edita (`409`); la base lo garantiza además
  con triggers (`0003_ms3`).
- Repuestos, proveedores e inventario siguen sin routers.

### 4.5 Evidencias multimedia (MS4)

| Capacidad | Cliente | Mecánico | Administrador |
|---|---|---|---|
| Recepción (subir) | ❌ 403 | ⚠️ solo de órdenes que atiende (se valida contra MS2) | ✅ |
| Consulta | ⚠️ las visibles para cliente, de sus órdenes (MS2) | ⚠️ las de órdenes que atiende (se valida contra MS2) | ✅ todas, incluidas las eliminadas |
| Cambiar `visible_cliente` | 📐 ❌ | 📐 ⚠️ salvo contexto `presupuesto` | 📐 ✅ |
| Eliminar | 📐 ❌ | 📐 ⚠️ solo las propias | 📐 ✅ |

Implementado en la Semana 5 (`routers/evidencias.py`, controles 3.1, 3.2, 3.3
y 3.4): la subida (`POST /evidencias`) exige rol **Mecánico o Administrador** y
el `403` se resuelve antes de leer el archivo. La pertenencia de la orden se
valida **contra MS2** (`services/ms4_evidencias/integracion_ms2.py`, mismo
contrato que MS3): MS4 reenvía el MISMO JWT a `GET {MS2_URL}/ordenes/{orden_id}`
en subir, listar, detalle y descarga; si MS2 responde 404/403 → `404` (orden
ajena o inexistente, sin enumerar) y si MS2 no responde → `503`. En
detalle/descarga el **Administrador no consulta a MS2** (auditoría: ve todo,
incluidas las eliminadas). La consulta aplica los tres filtros acumulativos del
cliente (`visible_cliente = true`, `estado = confirmada`, `eliminada_en IS
NULL`), el listado del administrador **incluye las eliminadas**, y la evidencia
ajena responde el **mismo 404** que una inexistente (no enumeración). Cambiar
`visible_cliente` y eliminar siguen sin endpoint (📐).

El detalle vigente está en
[`modelo-evidencias.md`](modelo-evidencias.md) §Reglas de visibilidad, que esta
matriz no sustituye:

| Rol | Qué ve | Qué puede hacer |
|---|---|---|
| Cliente | Evidencias de sus órdenes con `visible_cliente = true`, `estado = confirmada` y `eliminada_en IS NULL` | Solo lectura |
| Mecánico | Las confirmadas y no eliminadas de las órdenes que atiende | Subir, cambiar `visible_cliente` (salvo contexto `presupuesto`), eliminar las propias |
| Administrador | Todo, incluidas las eliminadas (auditoría) | Todo |

`obtener_principal_actual` ya está lista en
`services/ms4_evidencias/dependencies.py:24` y valida el token con el contrato
compartido, sin consultar la base de MS1.

## 5. Semántica de errores de autorización

| Código | Significado | Ejemplo |
|---|---|---|
| `401` | No hay token, es inválido o expiró. Se envía `WWW-Authenticate: Bearer` | Token ausente o con otro `JWT_SECRET_KEY` |
| `403` | Identidad válida, pero el rol no alcanza | Un Cliente intenta `POST /api/ordenes` |
| `404` | El recurso no existe **o** está fuera del alcance del solicitante | Un Cliente consulta la orden de otro Cliente |
| `409` | Conflicto de estado o de datos | Patente duplicada, correo registrado, autoasignación, orden en estado terminal |

Regla de no enumeración: `404` por falta de alcance **solo** donde la visibility
filter lo aplica (órdenes y evidencias). Un `403` de rol no revela existencia de
recursos: se rechaza antes de buscar nada.

## 6. Reglas para las tareas que dependen de esta matriz

Estas reglas dicen qué debe respetar cada tarea. No autorizan endpoints nuevos.

### 6.1 Permisos y asignación antes de mostrar acciones al mecánico

Cuando un cliente web o app móvil muestre acciones a un mecánico, debe atenerse
a esta matriz:

- El mecánico solo puede **leer** órdenes donde `mecanico_actual_id` coincide con su
  usuario. No existe ninguna acción de escritura habilitada para el rol `mecanico`.
- **Asignar y reasignar es solo del Administrador.** El mecánico no puede
  autoasignarse ni cambiar el responsable de una orden.
- No ofrecer acciones de cambio de estado: **no existe endpoint** de cambio general
  de estado. La única transición automática es la que dispara la primera asignación.
- No ofrecer listado de vehículos al mecánico: `GET /api/vehiculos/asignados` **no
  existe**.
- Ocultar una acción por rol es una medida de experiencia de usuario, **no** de
  seguridad. Cada endpoint que exponga esa acción debe repetir la comprobación en el
  servidor; confiar solo en la interfaz permite saltarse el permiso con `curl`.

### 6.2 Autorización y visibilidad de evidencias por rol

- Reutilizar `obtener_principal_actual` y `obtener_token_bearer` de
  `services/ms4_evidencias/dependencies.py`. **No** reimplementar la validación
  del token: `shared/auth.py` es el contrato único.
- La pertenencia de la orden al solicitante (dueño del vehículo / mecánico que
  la atiende) la decide MS2 con su `_filtro_visibilidad`: MS4 reenvía el mismo
  JWT a `GET {MS2_URL}/ordenes/{orden_id}`
  (`services/ms4_evidencias/integracion_ms2.py`, mismo contrato de MS3) —
  implementado en `routers/evidencias.py`.
- Respetar los tres filtros acumulativos del cliente: `visible_cliente = true`,
  `estado = confirmada` y `eliminada_en IS NULL`.
- Aplicar la misma no enumeración de MS2: orden o evidencia fuera del alcance →
  `404`, no `403`; en detalle/descarga el 404 de una evidencia ajena es IDÉNTICO
  al de una evidencia inexistente.
- Aplicar la regla multirol por unión, nunca por intersección.
- El administrador ve todas las evidencias, incluidas las eliminadas, y **no
  consulta a MS2** en detalle/descarga (auditoría).

## 7. Qué no autoriza este documento

- **No crea endpoints.** Ninguna fila marcada — ni 📐 autoriza una ruta.
- **No habilita roles ni permisos nuevos.** Los tres roles de `NombreRol` son los
  únicos válidos.
- **No cambia el contrato de la API.** Para rutas, cuerpos y errores ver
  [`contratos-api-gateway.md`](contratos-api-gateway.md).
- **No sustituye** la tabla «Roles y visibilidad actuales» de ese contrato, que
  describe el mismo comportamiento en el contexto de los endpoints publicados; si
  divergen, es un bug y hay que reportarlo.

## 8. Cómo mantener esta matriz

| Cambio en el código | Efecto en esta matriz |
|---|---|
| Se agrega o se cambia un endpoint | Actualizar la sección del servicio correspondiente |
| Se agrega un rol a `NombreRol` | Actualizar §3 y §4 completas |
| Cambia `_filtro_visibilidad` | Actualizar §4.3 y revisar §6 |
| Se implementa un router en MS3 o MS4 | Quitar 📐 y pasar las filas a ✅/⚠️/❌ con su endpoint |
| Cambia la visibilidad de evidencias | Actualizar §4.5 **y** `modelo-evidencias.md`, en el mismo cambio |
