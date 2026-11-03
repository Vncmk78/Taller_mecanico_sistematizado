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

La app móvil atiende a dos roles. El Administrador trabaja desde la web y queda
fuera de este catálogo.

| Rol | Qué hace en la app |
|---|---|
| Cliente | Se registra, entra, ve sus vehículos y órdenes, sigue el historial, revisa evidencias, aprueba o rechaza presupuestos y solicita cancelaciones |
| Mecánico | Entra, ve sus órdenes y vehículos asignados, cambia estados, registra bitácora y sube evidencias |

## 2. Catálogo de operaciones (25)

| Flujo | Operación | Cliente | Mecánico |
|---|---|:-:|:-:|
| Acceso | `POST /api/auth/register` | ✅ | — |
| Acceso | `POST /api/auth/login` | ✅ | ✅ |
| Acceso | `GET /api/auth/me` | ✅ | ✅ |
| Vehículos | `GET /api/vehiculos` | ✅ | 403 |
| Vehículos | `POST /api/vehiculos` | ✅ | 403 |
| Vehículos | `GET /api/vehiculos/{vehiculo_id}` | ✅ | 403 |
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

| | Cantidad |
|---|---:|
| Comprobaciones | 175 (25 × 7) |
| Cumplen | 168 |
| Brechas (`xfail` estricto) | 7, agrupadas en 4 hallazgos |

Lo que **sí** quedó confirmado para las 25 operaciones: todas están publicadas,
con la seguridad correcta, con esquema de éxito, y sus parámetros, cuerpos y
campos de respuesta coinciden 1:1 con el microservicio que las atiende.

## 4. Brechas detectadas

| ID | Operación | Brecha | Impacto en la app móvil |
|---|---|---|---|
| B-01 | `POST /api/auth/login` | MS1 responde `403` (cuenta sin roles), `422` (body inválido) y `429` (bloqueo temporal con `Retry-After`), pero la Gateway no los publica | La app no sabe que debe mostrar «cuenta bloqueada, reintenta en N s» ni distinguir una cuenta sin roles de credenciales malas |
| B-02 | `GET /api/vehiculos/{vehiculo_id}` | No publica `403` (rol sin Cliente) ni `422` (id inválido). El `403` tampoco lo declara MS2 | La app del mecánico no tiene documentado el `403` que recibirá si llama la ruta |
| B-03 | `GET` y `POST /api/ordenes/{orden_id}/bitacora` | El OpenAPI no trae ejemplo de éxito (sí existe en `contratos-api-gateway.md`) | Sin ejemplo en Swagger la app no puede generar mocks de la bitácora |
| B-04 | `POST /api/ordenes/{orden_id}/cancelacion` | Sin ejemplos de `201` (solicitud creada) ni `200` (solicitud repetida) | Igual que B-03 |

Las brechas quedan registradas en `_BRECHAS` del test. Se corrigen en la tarea
«Publicar una versión estable del contrato OpenAPI para integración»; al
corregirlas, la prueba pasa a XPASS y obliga a retirar la marca.

## 5. Observaciones (no son brechas del contrato publicado)

- **O-01 — Matriz desactualizada.** `matriz-autorizacion-roles.md` §4.2 dice que
  `GET /api/vehiculos/asignados` no existe; la ruta está implementada en MS2,
  publicada y documentada en `contratos-api-gateway.md`.
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
| Notificaciones push | Sin endpoint |
| Repuestos e inventario desde la app del mecánico | Publicados, pero no forman parte del flujo móvil acordado |

## 7. Cómo ejecutar la validación

```bash
cd backend
python -m pytest tests/test_contratos_integracion_iv.py -v
```

Resultado esperado hoy: `172 passed, 7 xfailed`.
