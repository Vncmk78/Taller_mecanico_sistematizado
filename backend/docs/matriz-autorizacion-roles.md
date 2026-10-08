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
| MS3 | 8003 | Presupuestos, repuestos, proveedores, inventario | **Sin endpoints** |
| MS4 | 8004 | Evidencias multimedia | **Sin endpoints de negocio** |

La Gateway **no valida el JWT**: se limita a reenviar la petición. Toda decisión de
autorización ocurre en el microservicio que atiende la ruta.

## 2. Fuentes de verdad

| Fuente | Qué define |
|---|---|
| `backend/shared/auth.py` | Los tres roles, la emisión del token y su validación. **Contrato único**: no reimplementar la validación del JWT en ningún servicio |
| `backend/shared/auth.py` → `NombreRol` | `cliente`, `mecanico`, `administrador`. No existe `role` en singular |
| `services/ms2_taller/services/ordenes.py` → `_filtro_visibilidad` | La visibilidad de órdenes por rol, con soporte multirol |
| `services/ms2_taller/dependencies.py` → `resolver_cliente_actual` | El guard de vehículos: exige rol Cliente y perfil local |
| `services/ms3_presupuestos/dependencies.py` → `requerir_roles` | Guard reutilizable de "al menos uno de estos roles" (aún sin usar) |
| `services/ms4_evidencias/dependencies.py` → `obtener_principal_actual` | Valida el token en MS4 (lista, sin endpoints que la usen) |
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
| `GET /api/auth/usuarios` (listar cuentas) | ❌ | ❌ | ✅ |
| `GET /api/auth/usuarios/{usuario_id}` (detalle de cualquier cuenta) | ❌ | ❌ | ✅ |
| `POST /api/auth/usuarios/{usuario_id}/roles` (asignar un rol) | ❌ | ❌ | ✅ |
| `DELETE /api/auth/usuarios/{usuario_id}/roles/{rol}` (retirar un rol) | ❌ | ❌ | ✅ |

Los cuatro endpoints de gestión de usuarios exigen el rol `administrador`
(`Depends(requerir_roles(NombreRol.ADMINISTRADOR))`): sin token responden `401`
y con un rol distinto, `403`. El listado y el detalle incluyen también las
cuentas sin roles (`roles: []`). Cada asignación o retirada queda registrada en
`historial_rol` con el administrador responsable y la fecha y hora.

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
| Cualquier endpoint de negocio | — | — | — |

MS3 **no tiene routers**. `requerir_roles(NombreRol.ADMINISTRADOR)` ya existe en
`services/ms3_presupuestos/dependencies.py:56` y es el guard previsto para cuando se
definan los endpoints, pero hoy ningún endpoint lo usa. La matriz no autoriza
ninguna ruta de MS3.

### 4.5 Evidencias multimedia (MS4)

| Capacidad | Cliente | Mecánico | Administrador |
|---|---|---|---|
| Recepción (subir) | 📐 | 📐 ⚠️ solo de órdenes que atiende | 📐 ✅ |
| Consulta | 📐 ⚠️ las visibles para cliente | 📐 ⚠️ las de órdenes que atiende | 📐 ✅ todas, incluidas eliminadas |
| Cambiar `visible_cliente` | 📐 ❌ | 📐 ⚠️ salvo contexto `presupuesto` | 📐 ✅ |
| Eliminar | 📐 ❌ | 📐 ⚠️ solo las propias | 📐 ✅ |

Todas las capacidades de MS4 están marcadas 📐: **la regla está definida, el
endpoint no existe**. El detalle vigente está en
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

- Reutilizar `obtener_principal_actual` de `services/ms4_evidencias/dependencies.py`.
  **No** reimplementar la validación del token: `shared/auth.py` es el contrato único.
- Reutilizar el patrón de `_filtro_visibilidad` de MS2 para el alcance por
  `mecanico_actual_id` y por vehículo del cliente, en lugar de inventar otro criterio.
- Respetar los tres filtros acumulativos del cliente: `visible_cliente = true`,
  `estado = confirmada` y `eliminada_en IS NULL`.
- Aplicar la misma no enumeración de MS2: evidencia fuera del alcance → `404`, no
  `403`.
- Aplicar la regla multirol por unión, nunca por intersección.

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
