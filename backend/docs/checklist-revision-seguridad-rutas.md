# Checklist de revisión de seguridad de rutas — API Gateway SGTM

Rama `DerisA` · revisión de backend · 12-11-2026 · base `1df4132`

Este documento revisa, una por una, las **94 operaciones HTTP que la API Gateway
publica hoy** (75 *paths*), y responde para cada una: ¿exige autenticación?,
¿qué rol?, ¿valida que el recurso sea del solicitante?, ¿valida la entrada?,
¿evita enumerar recursos? y ¿qué se expone en la respuesta o en la
documentación?

Es un documento de **revisión y seguimiento**: no cambia comportamiento. Los
hallazgos se registran con su evidencia y su recomendación, pero las
correcciones quedan fuera de este alcance.

---

## 1. Alcance y método

### 1.1 Qué se revisó

- Las **94 operaciones** publicadas por la Gateway (OpenAPI en
  `backend/gateway/openapi.py`), agrupadas por microservicio.
- Los *guards* reales de cada operación: dependencias de FastAPI resueltas en
  MS1–MS4 (autenticación, roles) y comprobaciones de propiedad/visibilidad
  dentro de `services/`.
- Los controles transversales de la Gateway: proxy, límite de cuerpo, CORS,
  manejo de errores, healthchecks y documentación.
- Las **rutas internas** `/interno/*` y las rutas con
  `include_in_schema=False` que no aparecen en el OpenAPI pero existen en los
  servicios.

### 1.2 Qué no se revisó

- `frontend/` y clientes móviles.
- Pruebas de penetración, análisis de dependencias (SCA), escaneo de imágenes
  o configuración de infraestructura/plataforma.
- Reglas de negocio internas de la máquina de estados (cubiertas en
  `docs/maquina-estados-ordenes.md`).
- Los estudios OWASP previos: sus hallazgos se referencian cuando aplican, no
  se repiten como nuevos.

### 1.3 Cómo se obtuvo el inventario

Se usó el OpenAPI que la propia Gateway construye (es la fuente que consumen
los clientes) y se contrastó con la introspección de las dependencias FastAPI
de cada microservicio, para ver el *guard* real y no solo lo documentado.

Reproducción del conteo:

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -c "from gateway.main import app; d=app.openapi(); ops=[(m,p) for p,v in d['paths'].items() for m in v if m in {'get','post','put','patch','delete'}]; print(len(d['paths']), len(ops))"
# 75 94
```

### 1.4 Criterios de cada columna

| Columna | Qué significa |
|---|---|
| **AuthN** | Cómo se establece la identidad: `JWT` (Bearer validado en el microservicio) o `Público` (por diseño, sin token). |
| **Rol** | Rol o roles que exige el guard. `cualquiera` = cualquier JWT válido, sin rol específico. |
| **Propiedad / visibilidad** | Comprobación de que el recurso pertenece al solicitante o cae dentro de su alcance (cliente dueño, mecánico asignado, administrador global). |
| **Validación** | DTO de entrada y límites de `Path`/`Query` relevantes para la seguridad. |
| **Estado** | Resultado del control revisado (ver leyenda). |

### 1.5 Leyenda

- ✅ **Cumple**: el control existe y es suficiente para lo que la ruta expone.
- ⚠️ **Cumple con observación**: hay control, pero queda una decisión
  pendiente, un límite ausente o una exposición menor (ver hallazgos).
- ❌ **No cumple**: falta un control de autorización o el control existente no
  protege el recurso (ver hallazgos).

### 1.6 Resumen

| Servicio | Operaciones | ✅ | ⚠️ | ❌ |
|---|---:|---:|---:|---:|
| Gateway (índice y salud) | 4 | 2 | 2 | 0 |
| MS1 — Autenticación y usuarios | 7 | 3 | 4 | 0 |
| MS1 — Notificaciones | 8 | 7 | 1 | 0 |
| MS2 — Clientes | 2 | 2 | 0 | 0 |
| MS2 — Vehículos | 5 | 5 | 0 | 0 |
| MS2 — Órdenes | 25 | 25 | 0 | 0 |
| MS3 — Presupuestos | 14 | 14 | 0 | 0 |
| MS3 — Inventario | 13 | 9 | 1 | 3 |
| MS3 — Repuestos | 6 | 6 | 0 | 0 |
| MS3 — Proveedores | 6 | 6 | 0 | 0 |
| MS4 — Evidencias | 4 | 4 | 0 | 0 |
| **Total** | **94** | **83** | **8** | **3** |

---

## 2. Controles transversales

| Control | Estado | Evidencia | Observación |
|---|---|---|---|
| Contrato único del JWT | ✅ | `backend/shared/auth.py:18-138` | Claims `sub`, `roles`, `exp`; emisión y validación en un solo módulo. |
| Respuestas 401/403 uniformes | ✅ | `backend/shared/errores_auth.py:17-26` | Mismo cuerpo y `WWW-Authenticate: Bearer`; no revelan la causa. |
| Autenticación en los cuatro MS | ✅ | `ms1_auth/dependencies.py:29`, `ms2_taller/dependencies.py:27`, `ms3_presupuestos/dependencies.py:40`, `ms4_evidencias/dependencies.py:27` | `HTTPBearer(auto_error=False)` + validación del token y del usuario. |
| La Gateway **no** valida el JWT | ✅ (por diseño) | `backend/gateway/routers/proxy.py:132-229`, `backend/gateway/rutas.py:1-20` | Solo enruta y reenvía `Authorization`; la autorización vive en cada microservicio. |
| Autorización por rol | ✅ | `requerir_roles(...)` en MS1–MS4 | Ver el detalle por operación en la sección 3. |
| Autorización por recurso | ⚠️ | `services/ms2_taller/services/ordenes.py:1247` (`_filtro_visibilidad`), `ms3_presupuestos/routers/presupuestos.py:93` (`_exigir_orden_del_cliente`), `ms4_evidencias/routers/evidencias.py:202` (`_accesible`) | Correcta en general; ver **H-01** en inventario. |
| No enumeración de recursos | ⚠️ | 404 uniforme en MS2/MS3/MS4; 401 genérico en login | El registro y el login sí permiten inferir si una cuenta existe (**H-03**). |
| Validación de entrada | ✅ | DTOs Pydantic en `schemas/`; `Path(gt=0)`, `Query(ge=..., le=...)`, enums | Sin cuerpos libres de identidad: el actor sale del JWT. |
| Límite de cuerpo en la Gateway | ✅ | `backend/gateway/routers/proxy.py:110-129` | Declarado y real (stream); 413/400 antes de reenviar. |
| CORS | ⚠️ | `backend/gateway/main.py:48-56`, `backend/gateway/config.py:76-96` | Orígenes explícitos + regex `https://*.vercel.app` con credenciales; ya analizado como OWASP-H5. |
| Errores sin detalle interno | ✅ | `backend/gateway/errores.py`, `backend/gateway/middleware.py` | Formato común con `request_id`; no se filtran DSN ni SQL. |
| Documentación interactiva | ⚠️ | `backend/gateway/main.py:37` (sin `docs_url=None`) | `/docs`, `/redoc` y `/openapi.json` son públicos (**H-05**). |
| *Rate limiting* transversal | ❌ | No hay límite en la Gateway; solo bloqueo por cuenta en `ms1_auth/services/autenticacion.py:120-226` | **H-04**. |
| Aislamiento de rutas internas | ⚠️ | HMAC con `hmac.compare_digest` y 503 si el secreto no está configurado | Depende de que los puertos de los MS no se publiquen (**H-02**). |
| Secretos de firma | ✅ | `JWT_SECRET_KEY: SecretStr = Field(min_length=32)` en los cuatro MS | Sin valor por defecto en el repositorio; se inyecta por entorno. |

---

## 3. Checklist por servicio

La identidad (`sub` → `usuario_id` y `roles`) sale siempre del JWT validado en
el microservicio. Salvo que se indique lo contrario, la validación de entrada es
un DTO Pydantic del directorio `schemas/` del servicio.

### 3.1 Gateway — índice y salud (4)

Guards: la Gateway solo responde estas rutas; el resto se reenvía
(`backend/gateway/routers/health.py:48-151`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `GET /` | Público | — | — | — | ✅ |
| `GET /api/health` | Público | — | — | — | ✅ |
| `GET /api/health/servicios` | Público | — | — | — | ⚠️ H-06 |
| `GET /api/health/servicios/{servicio}` | Público | — | — | nombre en lista blanca; 404 si no existe | ⚠️ H-06 |

### 3.2 MS1 — Autenticación y usuarios (7)

Guards: `obtener_principal_actual` (`ms1_auth/dependencies.py:29`) y
`requerir_roles` (`ms1_auth/dependencies.py:64`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/auth/register` | Público (por diseño) | — | — | DTO `RegistroClienteSolicitud` | ⚠️ H-03 |
| `POST /api/auth/login` | Público (por diseño) | — | — | DTO + bloqueo por cuenta (429 + `Retry-After`) | ⚠️ H-03 |
| `GET /api/auth/me` | JWT | cualquiera | solo el `usuario_id` del token | — | ✅ |
| `GET /api/auth/usuarios` | JWT | Administrador | — | sin paginación (devuelve la lista completa) | ✅ |
| `GET /api/auth/usuarios/{usuario_id}` | JWT | Administrador | 404 si no existe | `Path(gt=0)` | ✅ |
| `POST /api/auth/usuarios/{usuario_id}/roles` | JWT | Administrador | 404 si el usuario no existe | DTO con enum de rol | ⚠️ OWASP-H3 (auto-retiro) |
| `DELETE /api/auth/usuarios/{usuario_id}/roles/{rol}` | JWT | Administrador | 404 si no existe | enum en el path | ⚠️ OWASP-H3 (auto-retiro) |

### 3.3 MS1 — Notificaciones (8)

Guards: `obtener_principal_actual`; toda consulta filtra por
`principal.usuario_id` (`ms1_auth/routers/notificaciones.py:127-163`,
`ms1_auth/routers/entregas_notificaciones.py:75-175`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/notificaciones/dispositivos` | JWT | cualquiera | registro propio | `SecretStr` para el token push; plataforma enumerada | ✅ |
| `GET /api/notificaciones/dispositivos` | JWT | cualquiera | solo los propios | — | ✅ |
| `DELETE /api/notificaciones/dispositivos/{dispositivo_id}` | JWT | cualquiera | propio; 404 si es ajeno | `Path(gt=0)` | ✅ |
| `GET /api/notificaciones/{notificacion_id}/entregas` | JWT | cualquiera | propio (`propia()`); 404 si es ajena | `Path(gt=0)` | ✅ |
| `POST /api/notificaciones/{notificacion_id}/reintentos` | JWT | cualquiera | propio; 404 si es ajena | `Path(gt=0)` | ⚠️ sin límite de reintentos |
| `PATCH /api/notificaciones/leer-todas` | JWT | cualquiera | solo las propias | — | ✅ |
| `PATCH /api/notificaciones/{notificacion_id}/leer` | JWT | cualquiera | propio; 404 si es ajena | `Path(gt=0)` | ✅ |
| `GET /api/notificaciones` | JWT | cualquiera | solo las propias | paginación con tope | ✅ |

### 3.4 MS2 — Clientes (2)

Guards: rol Cliente explícito y `resolver_cliente_actual`
(`ms2_taller/routers/clientes.py:67`, `ms2_taller/dependencies.py`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/clientes/perfil` | JWT | Cliente | perfil propio; idempotente | DTO `PerfilClientePreparar`; 409 si el teléfono contradice el perfil | ✅ |
| `GET /api/clientes/perfil` | JWT | Cliente | perfil propio; 404 si aún no existe | — | ✅ |

### 3.5 MS2 — Vehículos (5)

Guards: `obtener_principal_actual` y `resolver_cliente_actual`
(`ms2_taller/routers/vehiculos.py:63-110`, `:132-174`, `:202-210`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/vehiculos` | JWT | Cliente | se registra a nombre del perfil propio | DTO; 409 patente duplicada | ✅ |
| `GET /api/vehiculos` | JWT | Cliente o Administrador | Cliente: solo los propios; Admin: todos; Mecánico: 403 | — | ✅ |
| `GET /api/vehiculos/asignados` | JWT | Mecánico | solo vehículos con orden asignada | — | ✅ |
| `GET /api/vehiculos/{vehiculo_id}` | JWT | cualquiera con visibilidad | Admin: cualquiera; Cliente: propio; Mecánico: asignado; 404 si no | `Path(gt=0)` | ✅ |
| `PATCH /api/vehiculos/{vehiculo_id}` | JWT | Cliente | solo propio; 404 si es ajeno | DTO `VehiculoActualizar` | ✅ |

### 3.6 MS2 — Órdenes (25)

Guards: visibilidad de dominio `_filtro_visibilidad`
(`ms2_taller/services/ordenes.py:1247-1265`) y comprobaciones de actor en
`services/`. El Administrador ve todo; el Cliente solo las órdenes de sus
vehículos; el Mecánico solo las que tiene asignadas.

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `GET /api/ordenes/nuevas-atenciones` | JWT | Administrador o Cliente | Admin: todas; Cliente: propias; Mecánico: 403 | paginación con tope | ✅ |
| `GET /api/ordenes/nuevas-atenciones/{solicitud_id}` | JWT | Administrador o Cliente | propias; 404 si es ajena | `Path(gt=0)` | ✅ |
| `POST /api/ordenes/nuevas-atenciones/{solicitud_id}/revision` | JWT | Administrador | — | DTO; 409 si ya fue revisada con otro contenido | ✅ |
| `POST /api/ordenes/nuevas-atenciones/{solicitud_id}/orden` | JWT | Administrador | — | — | ✅ |
| `POST /api/ordenes/{orden_id}/nueva-atencion` | JWT | Cliente | solo el dueño; 404 si es ajena | DTO; descripción de 1–2000 caracteres | ✅ |
| `POST /api/ordenes` | JWT | Administrador | — | DTO | ✅ |
| `GET /api/ordenes` | JWT | cualquiera | Admin: todas; Cliente: propias; Mecánico: asignadas | — | ✅ |
| `GET /api/ordenes/{orden_id}` | JWT | cualquiera | misma visibilidad; 404 si no | `Path(gt=0)` | ✅ |
| `PUT /api/ordenes/{orden_id}/mecanico` | JWT | Administrador | mecánico validado contra MS1 | DTO; 409 si excede capacidad | ✅ |
| `GET /api/ordenes/configuracion/capacidad/mecanicos` | JWT | Administrador | — | — | ✅ |
| `PUT /api/ordenes/configuracion/capacidad/mecanicos` | JWT | Administrador | — | DTO | ✅ |
| `GET /api/ordenes/configuracion/capacidad/ingresos-diarios` | JWT | Administrador | — | — | ✅ |
| `PUT /api/ordenes/configuracion/capacidad/ingresos-diarios` | JWT | Administrador | — | DTO | ✅ |
| `GET /api/ordenes/vehiculo/{vehiculo_id}/historial` | JWT | cualquiera | Cliente: vehículo propio; Mecánico: solo asignadas; 404 si no | `Path(gt=0)`; `limit` 1–100 | ✅ |
| `GET /api/ordenes/{orden_id}/historial` | JWT | cualquiera | visibilidad de la orden; 404 si no | `Path(gt=0)` | ✅ |
| `GET /api/ordenes/{orden_id}/bitacora` | JWT | cualquiera | visibilidad de la orden; 404 si no | `Path(gt=0)` | ✅ |
| `POST /api/ordenes/{orden_id}/bitacora` | JWT | Mecánico asignado o Administrador | 403/404 si no | DTO `BitacoraCrear` | ✅ |
| `PATCH /api/ordenes/{orden_id}/estado` | JWT | Administrador o Mecánico asignado | 403 si no (`_puede_cambiar_estado`) | DTO con evento permitido | ✅ |
| `POST /api/ordenes/{orden_id}/entrega` | JWT | Administrador | — | DTO | ✅ |
| `POST /api/ordenes/{orden_id}/devolucion` | JWT | Administrador | — | — | ✅ |
| `POST /api/ordenes/{orden_id}/cancelacion` | JWT | Cliente | solo el dueño; 404 si es ajena | DTO; motivo no vacío | ✅ |
| `GET /api/ordenes/cancelaciones/pendientes` | JWT | Administrador | — | — | ✅ |
| `POST /api/ordenes/{orden_id}/cancelacion/confirmacion` | JWT | Administrador | — | — | ✅ |
| `POST /api/ordenes/{orden_id}/decisiones-presupuesto` | JWT | Cliente | solo el dueño y solo su propia decisión; 404 si no | DTO; 409 si no aplica | ✅ |
| `POST /api/ordenes/{orden_id}/envios-presupuesto` | JWT | Administrador | envío verificado en MS3 antes de aplicar | DTO | ✅ |

### 3.7 MS3 — Presupuestos (14)

Guards: `_personal_del_taller`, `_solo_administrador`, `_solo_cliente` y
`_cualquier_rol` (`ms3_presupuestos/routers/presupuestos.py:74-77`). La
propiedad del Cliente se valida contra MS2 y se traduce a 404 para no revelar
existencia (`presupuestos.py:93-108`); el Mecánico además debe tener la orden
asignada (`_orden_para_el_personal`, `presupuestos.py:120-134`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/presupuestos` | JWT | Mecánico o Administrador | Mecánico: orden asignada; Admin: orden existente; 404 | DTO; 409 si ya hay presupuesto | ✅ |
| `GET /api/presupuestos` | JWT | cualquiera | personal: catálogo; Cliente: exige `orden_id` y ser dueño; 404 | `limite` con tope; `desde >= 0` | ✅ |
| `GET /api/presupuestos/ordenes/{orden_id}/primera-aprobacion` | JWT | Cliente o Administrador | Cliente: propietario; Admin: orden visible | `Path(gt=0)` | ✅ |
| `GET /api/presupuestos/{presupuesto_id}` | JWT | cualquiera | Cliente: sus órdenes y solo versiones enviadas; 404 | `Path(gt=0)` | ✅ |
| `GET /api/presupuestos/{presupuesto_id}/versiones/{numero}` | JWT | cualquiera | igual que el detalle; borradores invisibles al Cliente | `Path(ge=1)` | ✅ |
| `POST /api/presupuestos/{presupuesto_id}/versiones` | JWT | Mecánico o Administrador | Mecánico asignado; Admin cualquiera | DTO; 409 si hay borrador abierto | ✅ |
| `POST /api/presupuestos/{presupuesto_id}/modificacion` | JWT | Mecánico o Administrador | ídem | DTO; 409 si no es la última versión | ✅ |
| `PUT /api/presupuestos/{presupuesto_id}/versiones/{numero}/items` | JWT | Mecánico o Administrador | ídem; 409 si la versión no es borrador | DTO de ítems | ✅ |
| `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | JWT | Administrador | — | 409/503 según la orden | ✅ |
| `GET /api/presupuestos/{presupuesto_id}/envio-inicial` | JWT | Administrador | — | 409 si no hay envío pendiente | ✅ |
| `POST /api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion` | JWT | Administrador | — | 409/503; idempotente | ✅ |
| `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/decision` | JWT | Cliente | solo el dueño; 404 si no | DTO; 422 si rechaza sin motivo | ✅ |
| `GET /api/presupuestos/decisiones/{decision_id}` | JWT | Cliente | solo decisiones propias; 404 si no | `Path(gt=0)` | ✅ |
| `POST /api/presupuestos/decisiones/{decision_id}/aplicacion` | JWT | Cliente | solo decisiones propias; 404 si no | `Path(gt=0)`; 409/503 | ✅ |

### 3.8 MS3 — Inventario (13)

Guards: `_personal`, `_administrador` (`ms3_presupuestos/routers/inventario.py:67-68`).
`POST /movimientos` valida la asignación del Mecánico contra MS2
(`inventario.py:111-123`); las tres operaciones de reserva/consumo/liberación
**no** hacen esa validación (ver **H-01**).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/inventario/ordenes/{orden_id}/disponibilidad` | JWT | Administrador | reserva y coordinación contra MS2; 404/409 | `Path(gt=0)` | ✅ |
| `GET /api/inventario/ordenes/{orden_id}/disponibilidad` | JWT | Mecánico o Administrador | **sin verificar asignación**; revela si la orden tiene presupuesto | `Path(gt=0)` | ⚠️ H-01 |
| `POST /api/inventario/movimientos` | JWT | Mecánico o Administrador | ingreso/ajuste: solo Admin; Mecánico: solo orden asignada (MS2); 404/503 | DTO; `clave_operacion` idempotente | ✅ |
| `GET /api/inventario/movimientos` | JWT | Mecánico o Administrador | — | filtros + paginación con tope | ✅ |
| `GET /api/inventario/stock/{repuesto_id}` | JWT | Mecánico o Administrador | — | `Path(gt=0)` | ✅ |
| `GET /api/inventario/alertas` | JWT | Mecánico o Administrador | — | — | ✅ |
| `GET /api/inventario/umbral-general` | JWT | Mecánico o Administrador | — | — | ✅ |
| `PUT /api/inventario/umbral-general` | JWT | Administrador | — | DTO; 422 si el valor es inválido | ✅ |
| `GET /api/inventario/historial-umbral` | JWT | Mecánico o Administrador | — | filtros + paginación con tope | ✅ |
| `POST /api/inventario/disponibilidad` | JWT | Mecánico o Administrador | solo lectura; no mueve stock | DTO de ítems | ✅ |
| `POST /api/inventario/ordenes/{orden_id}/reserva` | JWT | Mecánico o Administrador | **sin verificar asignación** | `Path(gt=0)`; 404/409 | ❌ H-01 |
| `POST /api/inventario/ordenes/{orden_id}/consumos` | JWT | Mecánico o Administrador | **sin verificar asignación**; acepta repuestos del cuerpo | DTO + `clave_operacion`; 409 stock insuficiente | ❌ H-01 |
| `POST /api/inventario/ordenes/{orden_id}/liberacion` | JWT | Mecánico o Administrador | **sin verificar asignación** | DTO `clave_operacion` | ❌ H-01 |

### 3.9 MS3 — Repuestos (6)

Guards: `_lectura` (Mecánico o Administrador) y `_escritura` (Administrador),
`ms3_presupuestos/routers/repuestos.py:38-39`.

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `GET /api/repuestos` | JWT | Mecánico o Administrador | — | filtros + paginación con tope | ✅ |
| `POST /api/repuestos` | JWT | Administrador | — | DTO; 409 si hay duplicado | ✅ |
| `GET /api/repuestos/{repuesto_id}` | JWT | Mecánico o Administrador | — | `Path(gt=0)` | ✅ |
| `PATCH /api/repuestos/{repuesto_id}` | JWT | Administrador | — | DTO; 409 conflicto | ✅ |
| `DELETE /api/repuestos/{repuesto_id}` | JWT | Administrador | — | 409 si está en uso | ✅ |
| `GET /api/repuestos/{repuesto_id}/trazabilidad` | JWT | Mecánico o Administrador | — | `Path(gt=0)` | ✅ |

### 3.10 MS3 — Proveedores (6)

Guards: `_lectura` (Mecánico o Administrador) y `_escritura` (Administrador),
`ms3_presupuestos/routers/proveedores.py:36-37`.

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `GET /api/proveedores` | JWT | Mecánico o Administrador | — | filtros + paginación con tope | ✅ |
| `POST /api/proveedores` | JWT | Administrador | — | DTO; 409 si hay duplicado | ✅ |
| `GET /api/proveedores/{proveedor_id}` | JWT | Mecánico o Administrador | — | `Path(gt=0)` | ✅ |
| `PATCH /api/proveedores/{proveedor_id}` | JWT | Administrador | — | DTO; 409 conflicto | ✅ |
| `DELETE /api/proveedores/{proveedor_id}` | JWT | Administrador | — | 409 si está en uso | ✅ |
| `GET /api/proveedores/{proveedor_id}/trazabilidad` | JWT | Mecánico o Administrador | — | `Path(gt=0)` | ✅ |

### 3.11 MS4 — Evidencias (4)

Guards: rol al subir (`_personal_que_subira`,
`ms4_evidencias/routers/evidencias.py:168-181`), orden visible en MS2
(`_exigir_orden_accesible`, `:219-258`) y alcance de la evidencia
(`_accesible` → `es_visible_para`, `:202-210`).

| Operación | AuthN | Rol | Propiedad / visibilidad | Validación | Estado |
|---|---|---|---|---|---|
| `POST /api/evidencias` | JWT | Mecánico o Administrador | orden visible en MS2; 404 si no; 409 si la orden está cerrada; presupuesto de la misma orden | MIME y tamaño (413/415/422); multipart | ✅ |
| `GET /api/evidencias?orden_id=` | JWT | cualquiera | orden validada en MS2; Cliente: solo visibles y confirmadas; Admin: incluye eliminadas | `Query(gt=0)` | ✅ |
| `GET /api/evidencias/{evidencia_id}` | JWT | cualquiera | Admin exento de MS2; resto: orden visible + alcance; 404 sin enumeración | UUID en el path | ✅ |
| `GET /api/evidencias/{evidencia_id}/descarga` | JWT | cualquiera | mismo alcance; URL prefirmada con TTL de 300 s y `no-store` | UUID en el path | ✅ |

---

## 4. Rutas no publicadas que igual existen

### 4.1 Rutas internas `/interno/*`

No aparecen en el OpenAPI de la Gateway ni pueden alcanzarse por ella: el
catálogo de prefijos no incluye `interno` (`backend/gateway/rutas.py:56-95`), así
que `/api/interno/...` no resuelve a ningún servicio. Su protección es un
secreto compartido por cabecera `X-Service-Token`, comparado con
`hmac.compare_digest`; si el secreto no está configurado responden 503
(*fail-closed*).

| Servicio | Operación | Evidencia | Protección |
|---|---|---|---|
| MS1 | `POST /interno/eventos/ordenes/estado` | `ms1_auth/routers/notificaciones.py:42-56` | HMAC `EVENT_SHARED_SECRET`; 401/503 |
| MS1 | `POST /interno/eventos/nuevas-atenciones/revision` | `ms1_auth/routers/notificaciones.py:85-100` | HMAC `EVENT_SHARED_SECRET`; 401/503 |
| MS1 | `POST /interno/eventos/nuevas-atenciones/solicitud` | `ms1_auth/routers/notificaciones.py:102-116` | HMAC `EVENT_SHARED_SECRET`; 401/503 |
| MS1 | `POST /interno/eventos/ms3/aviso` | `ms1_auth/routers/avisos_ms3.py:47-60` | HMAC `MS3_EVENT_SHARED_SECRET`; 401/503 |
| MS2 | `GET /interno/notificaciones/ordenes/{orden_id}/destinatario` | `ms2_taller/routers/destinatarios_notificaciones.py:15-35` | HMAC `NOTIFICATION_LOOKUP_SECRET`; 401/503; respuesta sin PII |

Estado: ✅ el control de aplicación es correcto; ⚠️ la protección efectiva
depende de que esos puertos no se publiquen (ver **H-02**).

### 4.2 Rutas `include_in_schema=False` alcanzables por el proxy

| Servicio | Operación | Evidencia | Guard real |
|---|---|---|---|
| MS2 | `POST /api/ordenes/{orden_id}/disponibilidad-repuestos` | `ms2_taller/routers/ordenes.py:352-405` | JWT + Administrador + verificación de la reserva en MS3 |
| MS3 | `GET /api/inventario/ordenes/{orden_id}/disponibilidad/{clave_operacion}` | `ms3_presupuestos/routers/inventario.py:390-404` | JWT + Administrador |

Estado: ⚠️ **H-06**. No hay bypass (los guards se ejecutan igual), pero el
contrato público y el código pueden divergir sin que las pruebas de contrato lo
detecten.

---

## 5. Hallazgos

### H-01 — Reserva, consumo y liberación de stock sin verificación de asignación · **Alta**

**Qué pasa.** `POST /api/inventario/ordenes/{orden_id}/reserva`, `/consumos` y
`/liberacion` exigen solo rol Mecánico o Administrador
(`ms3_presupuestos/routers/inventario.py:242-299`) y nunca comprueban que el
Mecánico tenga la orden asignada. La operación equivalente
`POST /api/inventario/movimientos` sí lo hace antes de tocar stock
(`inventario.py:111-123`) y la matriz §4.4 lo exige para el Mecánico
(`docs/matriz-autorizacion-roles.md`, «solo órdenes asignadas»).

**Impacto.** Cualquier cuenta con rol Mecánico puede reservar, consumir o
liberar stock de una orden ajena con solo conocer su `orden_id`. En `consumos`
el cuerpo lo elige el llamante (`ConsumoOrden`), así que puede descontar
repuestos que no están en el presupuesto aprobado de esa orden, o dejar stock
bloqueado para otras. El `GET .../disponibilidad` de la misma familia también
revela si una orden ajena tiene presupuesto aprobado (⚠️ en la tabla).

**Recomendación.** Reutilizar la verificación ya existente
(`verificador.verificar_creacion_presupuesto`, como en `movimientos`) en las
cuatro rutas, antes de escribir stock; o restringirlas a Administrador si el
flujo es solo de coordinación. Añadir pruebas de acceso indebido por Mecánico
no asignado.

**Estado.** No corregido: este documento solo registra el hallazgo.

### H-02 — Rutas internas sin aislamiento de red garantizado · **Media (condicional)**

**Qué pasa.** Los cinco endpoints `/interno/*` están bien protegidos por HMAC,
pero cada microservicio escucha en su propio puerto (8001–8004) y el
`backend/docker-compose.yml` solo levanta bases de datos y MinIO. En ejecución
local, cualquier proceso que alcance esos puertos puede intentar la llamada; el
HMAC la rechaza, pero la superficie queda expuesta y depende de un secreto
compartido.

**Recomendación.** En despliegue, publicar únicamente la Gateway; para los MS,
mantener los puertos en la red interna. Verificar que el proveedor no exponga
8001–8004 por defecto. Documentar la rotación de los secretos
(`EVENT_SHARED_SECRET`, `MS3_EVENT_SHARED_SECRET`,
`NOTIFICATION_LOOKUP_SECRET`).

**Estado.** Depende de la configuración de despliegue, no del código de las
rutas.

### H-03 — Enumeración de cuentas en registro y login · **Media**

**Qué pasa.**

- `POST /api/auth/register` responde `409` cuando el correo ya está registrado
  (`ms1_auth/routers/auth.py:60-61`): permite comprobar si una cuenta existe.
- `POST /api/auth/login` distingue `401` (credenciales inválidas) de `403`
  (cuenta sin roles) y de `429` con `Retry-After` (cuenta bloqueada)
  (`ms1_auth/routers/auth.py:79-130`): las tres respuestas confirman que la
  cuenta existe.
- El bloqueo es por cuenta, no por IP: también sirve para negar el servicio a
  un usuario concreto.

Ya está analizado como OWASP-H1/H2 en
`docs/estudio-owasp-autenticacion-control-acceso.md`; se registra aquí porque
afecta a dos rutas publicadas.

**Recomendación.** Unificar la respuesta de login y decidir si el registro debe
responder igual ante un correo existente (por ejemplo, aceptar y enviar correo).
No implementado.

**Estado.** Pendiente de decisión de producto; no se tocó.

### H-04 — Sin rate limiting transversal · **Media**

**Qué pasa.** La Gateway reenvía sin límite de peticiones
(`gateway/routers/proxy.py:132-229`). El único control es el bloqueo por cuenta
del login (`ms1_auth/services/autenticacion.py:120-226`), que no cubre registro,
notificaciones, presupuestos ni evidencias.

**Impacto.** Fuerza bruta distribuida, abuso de endpoints costosos (subida de
evidencias, consultas históricas) y denegación de servicio.

**Recomendación.** Aplicar el límite en la capa de plataforma (proxy/CDN) o en
la Gateway, con cuotas distintas para login/registro y para el resto. No
implementado.

**Estado.** Pendiente de decisión de infraestructura.

### H-05 — Documentación interactiva y OpenAPI públicos · **Baja**

**Qué pasa.** `backend/gateway/main.py:37` crea `FastAPI(...)` sin desactivar
la documentación, por lo que `/docs`, `/redoc` y `/openapi.json` responden sin
autenticación. No exponen las rutas internas (el proxy es
`include_in_schema=False`), pero sí el inventario completo, los esquemas y los
ejemplos de todas las operaciones publicadas.

**Recomendación.** Decidir si en producción se deshabilitan
(`docs_url=None`, `redoc_url=None`, `openapi_url=None`) o se protegen. No
implementado.

**Estado.** Pendiente de decisión.

### H-06 — Rutas ocultas del OpenAPI alcanzables por el proxy · **Baja**

**Qué pasa.** `POST /api/ordenes/{orden_id}/disponibilidad-repuestos`
(`ms2_taller/routers/ordenes.py:352-355`) y
`GET /api/inventario/ordenes/{orden_id}/disponibilidad/{clave_operacion}`
(`ms3_presupuestos/routers/inventario.py:390-404`) existen y se ejecutan con sus
guards, pero no figuran en el contrato. Son rutas de coordinación entre
servicios que quedaron accesibles desde la misma URL pública.

**Riesgo.** Deriva de contrato: un cambio de guard o de forma no lo detectan las
pruebas basadas en OpenAPI; los clientes no deberían usarlas.

**Recomendación.** O documentarlas como internas y bloquearlas en la Gateway, o
moverlas a `/interno/*` con HMAC. No implementado.

**Estado.** Pendiente de decisión.

### H-07 — Healthchecks públicos con detalle de topología · **Baja / informativa**

**Qué pasa.** `GET /`, `GET /api/health`, `GET /api/health/servicios` y
`GET /api/health/servicios/{servicio}` son públicos
(`gateway/routers/health.py:48-151`). El último informa estado, latencias,
timeouts y prefijos de cada servicio; el índice enumera servicios y prefijos.
No expone URLs internas ni credenciales.

**Recomendación.** Aceptable para operación; si el despliegue es público,
valorar limitar el detalle a un healthcheck agregado. No implementado.

**Estado.** Observación.

---

## 6. Observaciones no bloqueantes

- `POST /api/notificaciones/{notificacion_id}/reintentos` permite reintentar sin
  límite ni ventana temporal; un usuario podría generar carga repetida sobre
  sus propios canales.
- `DELETE` y `PATCH` de roles permiten que un Administrador se quite su propio
  rol y deje el sistema sin administradores; ya registrado como OWASP-H3.
- El rol y la cuenta se validan al emitir el token, no en cada petición: un rol
  retirado sigue vigente hasta que expira el JWT (OWASP-H4). El diseño es
  stateless y está documentado.
- `S3_SECRET_KEY` de MS4 tiene un valor por defecto de desarrollo
  (`ms4_evidencias/config.py:45`); debe sobrescribirse por entorno en producción
  (ver `docs/minio-local.md`).
- El estudio
  `docs/estudio-pruebas-contrato-clientes-web-movil.md` declara un inventario
  anterior (28 paths / 25 operaciones); el inventario vigente es 75 paths /
  94 operaciones. No se corrigió en esta tarea.

---

## 7. Verificación realizada

- Conteo del OpenAPI de la Gateway: **75 paths / 94 operaciones**
  (comando en §1.3).
- Introspección de dependencias FastAPI de MS1–MS4 para confirmar el guard real
  de cada operación (autenticación, rol y verificadores de propiedad).
- Lectura de los routers y servicios citados en cada fila; las referencias
  `archivo:línea` corresponden a la base `1df4132` de la rama `DerisA`.
- No se ejecutaron pruebas de pytest para este documento: no cambia código ni
  contrato. La suite existente de autorización
  (`backend/tests/test_acceso_indebido_roles.py`) cubre parte de los controles
  listados, pero **no** cubre H-01.

---

## 8. Cómo mantener este documento

- Si se agrega o quita una operación en cualquier microservicio, actualizar la
  tabla del servicio y el resumen de §1.6.
- Si cambia un guard, actualizar la fila y la evidencia.
- Los hallazgos se cierran solo cuando el cambio está en la rama y con prueba
  que lo cubra; entonces se marca el estado y se referencia el commit.
- El inventario se puede regenerar con el comando de §1.3; si el número no
  coincide con 94, el documento quedó desactualizado.

---

## 9. Referencias

- `docs/matriz-autorizacion-roles.md` — qué puede hacer cada rol.
- `docs/contratos-api-gateway.md` — contrato escrito de rutas y errores.
- `docs/estudio-owasp-autenticacion-control-acceso.md` — hallazgos OWASP
  heredados (H1–H6).
- `docs/checklist-seguridad-evidencias.md` — checklist específico de MS4.
- `gateway/openapi.py`, `gateway/rutas.py`, `gateway/routers/proxy.py` — fuente
  del inventario y del enrutamiento.
- `shared/auth.py`, `shared/errores_auth.py` — contrato único del JWT y de las
  respuestas 401/403.
