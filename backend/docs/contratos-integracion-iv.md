# Contratos necesarios para Taller de Integración IV (app móvil)

**Semana 8 — Validar contratos necesarios para Taller de Integración IV.**

La app móvil de Integra IV consume la misma API Gateway que el frontend web
(`/api/*`). Este documento fija **qué operaciones necesita la app**, **qué se
validó de cada una** y **qué brechas quedan** en el contrato publicado.

- Catálogo ejecutable: `gateway/contratos/integracion_iv.py`
- Validación automática: `tests/test_contratos_integracion_iv.py`
- Contrato general: [`contratos-api-gateway.md`](contratos-api-gateway.md)
- Quién puede qué: [`matriz-autorizacion-roles.md`](matriz-autorizacion-roles.md)

---

## 1. Alcance

El contrato 3.0.0 agrega una restricción a la creación administrativa de órdenes:
solo una activa por vehículo. `POST /api/ordenes` no pertenece al catálogo móvil,
pero debe coordinarse la actualización de versión y verificar los recorridos
de consulta. No se modifican los ocho estados ni las respuestas de éxito.

La app móvil atiende a dos roles. El Administrador trabaja desde la web y queda
fuera de este catálogo.

| Rol | Qué hace en la app |
|---|---|
| Cliente | Se registra, entra, ve sus vehículos y órdenes, sigue el historial, revisa evidencias, aprueba o rechaza presupuestos y solicita cancelaciones |
| Mecánico | Entra, ve sus órdenes y vehículos asignados, cambia estados, registra bitácora y sube evidencias |

La versión 3.0.0 incorpora también las solicitudes de nueva atención del Cliente
(propiedad, descripción de 1–2000 caracteres, reintento idéntico 200 y creación 201),
su listado paginado y detalle. Los estados son pendiente/aceptada/rechazada; solicitar
no crea una orden ni reserva cupo. Una aceptada sigue bloqueando otra solicitud sobre
el mismo antecedente aunque ya tenga orden generada. Una rechazada permite otra.

Los avisos se consultan con `limite`, `offset` y `solo_no_leidas`; la fecha es
`creado_en`. `leida` y `leida_en` se conservan en MS1. Los PATCH de lectura responden
204 sin cuerpo, son idempotentes y un aviso ajeno devuelve 404.

**Validación móvil pendiente:** estas comprobaciones son de API y navegador web.
No acreditan recepción push ni funcionamiento de un APK. Falta el dispositivo/app
de Integración IV y la configuración del proveedor de push.

El contrato incluye el registro autenticado de dispositivos, su desactivación
al cerrar sesión y la consulta/reintento de canales propios. Las alertas de stock
pueden tener `orden_id`/`vehiculo_id` nulos; las referencias a presupuesto,
solicitud y repuesto son anulables. Ver [notificaciones-canales.md](notificaciones-canales.md)
para cuerpos, credenciales, estados y coordinación móvil.

## 2. Catálogo de operaciones (38)

| Flujo | Operación | Cliente | Mecánico |
|---|---|:-:|:-:|
| Nuevas atenciones | `POST /api/ordenes/{orden_id}/nueva-atencion` | ✅ | — |
| Nuevas atenciones | `GET /api/ordenes/nuevas-atenciones` | ✅ | — |
| Nuevas atenciones | `GET /api/ordenes/nuevas-atenciones/{solicitud_id}` | ✅ | — |
| Dispositivos | `POST /api/notificaciones/dispositivos` | ✅ | ✅ |
| Dispositivos | `GET /api/notificaciones/dispositivos` | ✅ | ✅ |
| Dispositivos | `DELETE /api/notificaciones/dispositivos/{dispositivo_id}` | ✅ | ✅ |
| Canales | `GET /api/notificaciones/{notificacion_id}/entregas` | ✅ | ✅ |
| Canales | `POST /api/notificaciones/{notificacion_id}/reintentos` | ✅ | ✅ |
| Avisos | `GET /api/notificaciones` | ✅ | ✅ |
| Avisos | `PATCH /api/notificaciones/{notificacion_id}/leer` | ✅ | ✅ |
| Avisos | `PATCH /api/notificaciones/leer-todas` | ✅ | ✅ |
| Acceso | `POST /api/auth/register` | ✅ | — |
| Acceso | `POST /api/auth/login` | ✅ | ✅ |
| Acceso | `GET /api/auth/me` | ✅ | ✅ |
| Acceso | `POST /api/clientes/perfil` ⁴ | ✅ | 403 |
| Acceso | `GET /api/clientes/perfil` | ✅ | 403 |
| Vehículos | `GET /api/vehiculos` | ✅ | 403 |
| Vehículos | `POST /api/vehiculos` | ✅ | 403 |
| Vehículos | `GET /api/vehiculos/{vehiculo_id}` | ✅ | ✅ ³ |
| Vehículos | `PATCH /api/vehiculos/{vehiculo_id}` | ✅ | 403 |
| Vehículos | `GET /api/vehiculos/asignados` | 403 | ✅ |
| Órdenes | `GET /api/ordenes` | ✅ | ✅ |
| Órdenes | `GET /api/ordenes/{orden_id}` | ✅ | ✅ |
| Órdenes | `GET /api/ordenes/{orden_id}/historial` | ✅ | ✅ |
| Órdenes | `POST /api/ordenes/{orden_id}/cancelacion` | ✅ | 403 |
| Trabajo del mecánico | `PATCH /api/ordenes/{orden_id}/estado` | 403 | ✅ |
| Trabajo del mecánico | `GET /api/ordenes/{orden_id}/bitacora` | ✅ | ✅ |
| Trabajo del mecánico | `POST /api/ordenes/{orden_id}/bitacora` | 403 | ✅ |
| Evidencias | `POST /api/evidencias` | 403 | ✅ |
| Evidencias | `GET /api/evidencias?orden_id=` | ✅ | ✅ |
| Evidencias | `GET /api/evidencias/{evidencia_id}` | ✅ | ✅ |
| Evidencias | `GET /api/evidencias/{evidencia_id}/descarga` | ✅ | ✅ |
| Presupuestos | `GET /api/presupuestos` | ✅ ¹ | ✅ |
| Presupuestos | `GET /api/presupuestos/{presupuesto_id}` | ✅ | ✅ |
| Presupuestos | `GET /api/presupuestos/{presupuesto_id}/versiones/{numero}` | ✅ | ✅ |
| Presupuestos | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/decision` | ✅ | 403 |
| Presupuestos | `GET /api/presupuestos/decisiones/{decision_id}` | ✅ | 403 |
| Presupuestos | `POST /api/presupuestos/decisiones/{decision_id}/aplicacion` | ✅ ² | 403 |

¹ El Cliente debe enviar siempre `orden_id`; el parámetro es opcional en el
esquema porque Mecánico y Administrador pueden listar sin él.
² Solo para reintentar cuando la decisión responde `503` con
`decision_registrada=true` (nunca se decide dos veces).
³ Solo los vehículos de sus órdenes asignadas; cualquier otro responde `404`.
⁴ Paso obligatorio del Cliente (contrato 2.2.0); ver «Registro y perfil Cliente».

### Registro y perfil Cliente (desde 2.2.0)

MS1 guarda la cuenta y MS2 guarda aparte el perfil Cliente que exigen
vehículos y órdenes (sistematización §4.1). Registrarse **no** crea ese perfil:
hasta 2.1.0 solo lo creaba el script de semilla, y un Cliente nuevo recibía
`404` en `/api/vehiculos`. La app debe seguir esta secuencia:

1. `POST /api/auth/register` (`email`, `password`, `full_name`; sin roles).
2. `POST /api/auth/login`.
3. Si `user.roles` incluye `cliente`: `POST /api/clientes/perfil` con `{}` o
   `{"telefono": "..."}` **en cada inicio de sesión**, antes de vehículos u
   órdenes. Es idempotente: `201` si lo creó, `200` si ya existía.
4. Si responde `500`, `502`, `503` o `504`, la cuenta ya existe: mostrar
   reintentar sin volver a registrarse. Un `409` significa que el perfil existe
   con otro teléfono (no se sobrescribe): se puede continuar.
5. `GET /api/clientes/perfil` solo consulta (`404` si aún no se preparó).

La identidad sale del JWT: el body rechaza `usuario_id`, `cliente_id` o roles
con `422`. El Mecánico recibe `403`.

## 3. Qué se validó

Cada operación pasa siete comprobaciones contra el `/openapi.json` de la
Gateway y contra el OpenAPI real del microservicio dueño (in-process, sin
levantar servicios):

| Comprobación | Regla |
|---|---|
| `publicada` | La ruta y el método existen en `/openapi.json` |
| `seguridad` | Protegidas con `bearerAuth`; `register` y `login` sin seguridad |
| `respuesta_exito` | Hay un 2xx `application/json` con esquema |
| `ejemplo_exito` | El 2xx trae ejemplo (la app lo usa como mock) |
| `estados` | Se publican 401 (protegidas), 403 (si un rol móvil es rechazado), 404 (con parámetros de ruta), 422 (con parámetros o body), 502 y 504, más los propios de cada flujo (409, 413, 415, 429, 503) |
| `estados_microservicio` | Todo estado que declara el microservicio también lo publica la Gateway |
| `campos_microservicio` | Parámetros, campos del body y de la respuesta 2xx y su obligatoriedad coinciden con el microservicio |

### Resultado

| | Validación inicial | Versión estable 1.0.0 |
|---|---:|---:|
| Comprobaciones | 175 (25 × 7) | 175 (25 × 7) |
| Cumplen | 168 | **175** |
| Brechas abiertas | 7 (4 hallazgos) | **0** |

Las 25 operaciones están publicadas, con la seguridad correcta, con esquema y
ejemplo de éxito, con los estados que la app debe manejar, y sus parámetros,
cuerpos y campos de respuesta coinciden 1:1 con el microservicio que las
atiende.

## 4. Brechas detectadas (todas corregidas en 1.0.0)

| ID | Operación | Brecha | Impacto en la app móvil | Estado |
|---|---|---|---|---|
| B-01 | `POST /api/auth/login` | MS1 responde `403` (cuenta sin roles), `422` (body inválido) y `429` (bloqueo temporal con `Retry-After`), pero la Gateway no los publicaba | La app no sabía que debe mostrar «cuenta bloqueada, reintenta en N s» ni distinguir una cuenta sin roles de credenciales malas | Corregida en 1.0.0 |
| B-02 | `GET /api/vehiculos/{vehiculo_id}` | No publicaba `422` (identificador inválido) que MS2 sí declara | Sin el `422` la app no distingue un id mal formado de un vehículo inexistente | Corregida en 1.0.0 |
| B-03 | `GET` y `POST /api/ordenes/{orden_id}/bitacora` | El OpenAPI no traía ejemplo de éxito (sí existía en `contratos-api-gateway.md`) | Sin ejemplo en Swagger la app no podía generar mocks de la bitácora | Corregida en 1.0.0 |
| B-04 | `POST /api/ordenes/{orden_id}/cancelacion` | Sin ejemplos de `201` (solicitud creada) ni `200` (solicitud repetida) | Igual que B-03 | Corregida en 1.0.0 |

Corrección al catálogo inicial: B-02 incluía un supuesto `403` para el
Mecánico. Revisando MS2, el endpoint no rechaza por rol: el Mecánico ve los
vehículos de sus órdenes asignadas y el resto responde `404`. El catálogo se
corrigió y el ejemplo de `403` que tenía el OpenAPI se retiró.

`_BRECHAS` del test queda vacío. Una brecha nueva se registra ahí como `xfail`
estricto con un ID nuevo (B-05, …).

## 5. Observaciones (no son brechas del contrato publicado)

- **O-01 — Matriz desactualizada.** `matriz-autorizacion-roles.md` §4.2 dice que
  `GET /api/vehiculos/asignados` no existe; la ruta está implementada en MS2,
  publicada y documentada en `contratos-api-gateway.md`. **Corregida en Semana 9**:
  la matriz ya refleja la ruta y el cambio de estado del Mecánico.
- **O-02 — La app no llama a `POST /api/ordenes/{orden_id}/decisiones-presupuesto`.**
  Lo invoca MS3 al registrar la decisión; la app decide solo por MS3
  (`.../versiones/{numero}/decision`) y reintenta por `.../aplicacion`.
- **O-03 — Cierre de sesión.** No hay endpoint de logout: el JWT no tiene estado
  y la app cierra sesión borrando el token local. Ante un `401` debe limpiar
  la sesión (RF-05).

## 6. Fuera del contrato

Capacidades del Cliente o del Mecánico **sin endpoint publicado**. La app no
debe consumir ninguna ruta no publicada aunque responda:

| Capacidad | Estado |
|---|---|
| Solicitar hora / agendar ingreso (Cliente) | Sin endpoint |
| Notificaciones push | Registro propio de dispositivos y resultados de canales implementados; recepción en APK/FCM real pendiente. |
| Repuestos e inventario desde la app del mecánico | Publicados, pero no forman parte del flujo móvil acordado |

## 7. Cómo ejecutar la validación

```bash
cd backend
python -m pytest tests/test_contratos_integracion_iv.py -v
```

Resultado esperado hoy: `179 passed`.
