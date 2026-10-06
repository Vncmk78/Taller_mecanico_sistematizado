# 🧪 TAREA 7: Pruebas de Acceso No Autorizado y Acceso Cruzado

**Objetivo:** demostrar que un usuario autenticado **no** puede operar fuera de
sus permisos ni ver datos de otro usuario.

---

> ⚠️ **Por qué esta tarea estaba bloqueada**
>
> La primera versión de este documento probaba contra un monolito **Node/Express**
> en `http://localhost:3001` con endpoints que **no existen** en el sistema
> actual: `GET /api/auth/users`, `GET /api/auth/users/:role`,
> `GET /api/orders/me`, `PATCH /api/orders/:id`. Además mandaba `"role"` en el
> registro, que el MS1 real rechaza con `422` porque los roles se asignan en el
> servidor, y esperaba `{"error": ...}` cuando el sistema devuelve
> `{"detail": ...}`. Los 15 tests de esa versión fallaban en el primer paso.
>
> Esta versión ejecuta **las mismas 15 intenciones** contra la arquitectura
> vigente (Gateway + MS1 + MS2 en FastAPI). Cada test original queda trazado en
> la [matriz de equivalencia](#matriz-de-equivalencia); nada se perdió.

---


## ⚡ Versión automática de la parte de autenticación

Los 15 tests de abajo cubren **autorización por rol y acceso cruzado**, que
requieren las tres identidades sembradas y por eso son manuales. La parte de
**autenticación** (casos válidos y rechazados de la Gateway hacia MS1) sí es
automatizable, y existe como script ejecutable:

```bash
# con la Gateway en :8000 y MS1 en :8001 levantados
cd backend
python scripts/prueba_comunicacion_smoke.py
```

Hace **33 comprobaciones** sobre HTTP real y devuelve código 0 si todas pasan, 1
si alguna falla. Cubre, contra la Gateway:

- **Válidos:** registro (201, el rol lo asigna el servidor), login (200, token
  `bearer`), `/me` con token válido, el token cumple el contrato de claims
  (`sub` texto con entero, `roles` lista, `exp`; y sin `role`, `id` ni `email`),
  la Gateway es transparente frente a MS1 directo, y la `Authorization` llega al
  microservicio de destino.
- **Rechazados:** correo duplicado (409), `role` en el cuerpo (422), contraseña
  corta (422), correo inválido (422), contraseña incorrecta (401), usuario
  inexistente con el **mismo** mensaje que contraseña incorrecta (no enumera),
  `/me` sin token (401 y no 403), token malformado (401), token firmado con otra
  clave (401) y token expirado (401).

Dos variables de entorno opcionales: `MS1_JWT_SECRET_KEY` habilita el caso de
token expirado (sin ella se reporta OMITIDO, no fallido, porque sin la clave real
el rechazo probaría la firma y no la expiración), y `MS1_URL` / `GATEWAY_URL`
apuntan a otros puertos si no usan los de por defecto.

Este script **no sustituye** a los 15 tests de abajo ni a las 304 pruebas de
`pytest`: sirve para comprobar en un despliegue que la cadena completa responde.

---
## 📋 Setup

### 1. Levantar los servicios

```bash
cd backend
docker compose up --build -d
docker compose ps        # espera a que ms1, ms2 y gateway estén "healthy"
```

| Servicio | Puerto | Rol |
|---|---|---|
| Gateway | `8000` | Único punto de entrada; solo enruta |
| MS1 Auth | `8001` | Registro, login, `/auth/me` |
| MS2 Taller | `8002` | Vehículos y órdenes |

Todas las peticiones del documento van **contra la Gateway** (`:8000`), que es
como consumen el frontend y la app móvil. La Gateway reenvía `Authorization`
sin validarlo; valida cada microservicio.

### 2. Crear las tres identidades de prueba

El registro público **solo puede crear clientes**, así que las cuentas de
mecánico y administrador se crean con el seed, que además crea el perfil
`Cliente` en MS2 (las bases de MS1 y MS2 están separadas):

```bash
cd backend
python scripts/seed_usuarios_prueba.py
```

| Identidad | Correo | Contraseña | Rol |
|---|---|---|---|
| Cliente | `cliente@pruebas.cl` | `ClientePrueba123!` | `cliente` |
| Mecánico | `mecanico@pruebas.cl` | `MecanicoPrueba123!` | `mecanico` |
| Administrador | `administrador@pruebas.cl` | `AdminPrueba123!` | `administrador` |

### 3. Obtener los tres tokens

```bash
API=http://localhost:8000/api

TOKEN_CLIENTE=$(curl -s -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"cliente@pruebas.cl","password":"ClientePrueba123!"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

TOKEN_MECANICO=$(curl -s -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"mecanico@pruebas.cl","password":"MecanicoPrueba123!"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

TOKEN_ADMIN=$(curl -s -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"administrador@pruebas.cl","password":"AdminPrueba123!"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

### 4. Registrar un segundo cliente y darle un vehículo

Hace falta un segundo propietario para probar el acceso cruzado.

```bash
# Registro público: sin "role", el servidor asigna "cliente". Repetir con otro
# correo devuelve 409.
curl -s -X POST $API/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"cliente2@pruebas.cl","password":"Cliente2Prueba123!","full_name":"Cliente Dos"}'

TOKEN_CLIENTE2=$(curl -s -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"cliente2@pruebas.cl","password":"Cliente2Prueba123!"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

Cada cliente registra **su propio** vehículo (el propietario se toma siempre del
JWT, nunca del body):

```bash
VEH_CLIENTE=$(curl -s -X POST $API/vehiculos \
  -H "Authorization: Bearer $TOKEN_CLIENTE" -H 'Content-Type: application/json' \
  -d '{"patente":"AA1111","marca":"Toyota","modelo":"Corolla","anio":2018,"kilometraje":45000}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["vehiculo_id"])')

VEH_CLIENTE2=$(curl -s -X POST $API/vehiculos \
  -H "Authorization: Bearer $TOKEN_CLIENTE2" -H 'Content-Type: application/json' \
  -d '{"patente":"BB2222","marca":"Honda","modelo":"Civic","anio":2020,"kilometraje":20000}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["vehiculo_id"])')
```

---

## ✅ Autorización por rol (tests 1, 2, 3, 9, 10)

La operación reservada al Administrador es **crear una orden** y **asignar su
mecánico**. No existe un endpoint de listado de usuarios: en esta arquitectura
MS1 no expone los usuarios de otros servicios.

### TEST 1 — Cliente NO puede crear una orden (reservada al Administrador)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/ordenes \
  -H "Authorization: Bearer $TOKEN_CLIENTE" -H 'Content-Type: application/json' \
  -d "{\"vehiculo_id\":$VEH_CLIENTE}"
```

**Esperado: `403`**
```json
{ "detail": "No tienes permiso para realizar esta operación" }
```
**Status:** ❌ ACCESO DENEGADO ✅

### TEST 2 — Mecánico NO puede crear una orden

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/ordenes \
  -H "Authorization: Bearer $TOKEN_MECANICO" -H 'Content-Type: application/json' \
  -d "{\"vehiculo_id\":$VEH_CLIENTE}"
```

**Esperado: `403`** — mismo cuerpo que el test 1.
**Status:** ❌ ACCESO DENEGADO ✅

### TEST 3 — Administrador SÍ puede crear una orden

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/ordenes \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H 'Content-Type: application/json' \
  -d "{\"vehiculo_id\":$VEH_CLIENTE}"
```

**Esperado: `201`**
```json
{
  "orden_id": 1, "vehiculo_id": 12, "ingreso_id": 1, "estado_codigo": 1,
  "mecanico_actual_id": null, "creado_por_id": 99,
  "creado_en": "...", "actualizado_en": "..."
}
```
La orden nace en `Recibido` (`estado_codigo: 1`) y **sin** mecánico.
**Status:** ✅ ACCESO PERMITIDO ✅

```bash
ORDEN_CLIENTE=$(curl -s -X POST $API/ordenes \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H 'Content-Type: application/json' \
  -d "{\"vehiculo_id\":$VEH_CLIENTE}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["orden_id"])')

ORDEN_CLIENTE2=$(curl -s -X POST $API/ordenes \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H 'Content-Type: application/json' \
  -d "{\"vehiculo_id\":$VEH_CLIENTE2}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["orden_id"])')
```

### TEST 9 — Cliente NO puede asignar mecánico (reservado al Administrador)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT $API/ordenes/$ORDEN_CLIENTE/mecanico \
  -H "Authorization: Bearer $TOKEN_CLIENTE" -H 'Content-Type: application/json' \
  -d '{"mecanico_id":50}'
```

**Esperado: `403`**
**Status:** ❌ ACCESO DENEGADO ✅

### TEST 10 — Administrador SÍ puede asignar mecánico

```bash
MEC_ID=$(curl -s $API/auth/me -H "Authorization: Bearer $TOKEN_MECANICO" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')

curl -s -o /dev/null -w '%{http_code}\n' -X PUT $API/ordenes/$ORDEN_CLIENTE/mecanico \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H 'Content-Type: application/json' \
  -d "{\"mecanico_id\":$MEC_ID,\"observacion\":\"Asignacion inicial\"}"
```

**Esperado: `200`**, con `estado_codigo: 2` (`Esperando diagnóstico`) y
`mecanico_actual_id` igual a `$MEC_ID`. La primera asignación avanza el estado y
deja registro en el historial.
**Status:** ✅ ACCESO PERMITIDO ✅

---

## ✅ Propiedad del recurso y acceso cruzado (tests 5, 6, 7, 8)

> **Corrección importante respecto a la versión original:** el acceso a una orden
> ajena responde **`404`, no `403`**, y es deliberado. Un `403` confirmaría que
> la orden existe; el `404` hace que una orden ajena y una orden inexistente sean
> indistinguibles, de modo que no se puede usar la API para enumerar órdenes de
> otros clientes. El `403` queda reservado para "te autenticaste bien, pero tu
> rol no permite esta operación" (tests 1, 2, 9).

### TEST 4 — Crear órdenes para la prueba de propiedad

Hecho en el setup: `$ORDEN_CLIENTE` (vehículo del cliente 1) y
`$ORDEN_CLIENTE2` (vehículo del cliente 2).

### TEST 5 — Cliente NO puede ver la orden de otro cliente → `404`

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/ordenes/$ORDEN_CLIENTE2 \
  -H "Authorization: Bearer $TOKEN_CLIENTE"
```

**Esperado: `404`**
```json
{ "detail": "Orden no encontrada" }
```

Idéntico a consultar un id inexistente, por ejemplo `GET $API/ordenes/999999`:
también `404` con el mismo cuerpo. La diferencia entre "no existe" y "no es
tuyo" es indistinguible desde fuera.

**Status:** ❌ NO REVELADO ✅ (seguridad funcionando)

### TEST 6 — Cliente SÍ ve su propia orden

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/ordenes/$ORDEN_CLIENTE \
  -H "Authorization: Bearer $TOKEN_CLIENTE"
```

**Esperado: `200`** con el detalle de su orden.
**Status:** ✅ ACCESO PERMITIDO ✅

### TEST 7 — Mecánico NO ve una orden que no le asignaron → `404`

```bash
# $ORDEN_CLIENTE2 no tiene mecánico responsable
curl -s -o /dev/null -w '%{http_code}\n' $API/ordenes/$ORDEN_CLIENTE2 \
  -H "Authorization: Bearer $TOKEN_MECANICO"
```

**Esperado: `404`**

Y tampoco puede reasignar el responsable, porque esa operación es del
Administrador:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT $API/ordenes/$ORDEN_CLIENTE2/mecanico \
  -H "Authorization: Bearer $TOKEN_MECANICO" -H 'Content-Type: application/json' \
  -d "{\"mecanico_id\":$MEC_ID}"
```

**Esperado: `403`**
**Status:** ❌ ACCESO DENEGADO ✅

### TEST 8 — Administrador ve cualquier orden

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/ordenes/$ORDEN_CLIENTE2 \
  -H "Authorization: Bearer $TOKEN_ADMIN"
```

**Esperado: `200`**
**Status:** ✅ ACCESO PERMITIDO ✅

---

## ✅ Autenticación: sin token y con token inválido (tests 11, 12)

### TEST 11 — Sin token

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/auth/me
curl -s -o /dev/null -w '%{http_code}\n' $API/ordenes
```

**Esperado: `401`**, con cabecera `WWW-Authenticate: Bearer`
```json
{ "detail": "No se proporcionó un token de acceso" }
```
**Status:** ❌ NO AUTENTICADO ✅

### TEST 12 — Token inválido

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/auth/me \
  -H "Authorization: Bearer token_falso_123"
```

**Esperado: `401`**
```json
{ "detail": "Token inválido o expirado" }
```

Un token expirado, con firma inválida, o con `sub`/`roles` mal formados producen
**el mismo** `401`: no se le dice al atacante qué parte falló.

**Status:** ❌ TOKEN INVÁLIDO ✅

---

## ✅ Segregación de datos en el listado (tests 13, 14, 15)

### TEST 13 — Cliente ve solo sus órdenes

```bash
curl -s $API/ordenes -H "Authorization: Bearer $TOKEN_CLIENTE" \
  | python -c 'import sys,json; d=json.load(sys.stdin); print(len(d), [o["orden_id"] for o in d])'
```

**Esperado:** solo `$ORDEN_CLIENTE`. La orden del cliente 2 no aparece.
**Status:** ✅ ACCESO RESTRINGIDO A LO SUYO ✅

### TEST 14 — Mecánico ve solo las órdenes asignadas

```bash
curl -s $API/ordenes -H "Authorization: Bearer $TOKEN_MECANICO" \
  | python -c 'import sys,json; d=json.load(sys.stdin); print(len(d), [o["orden_id"] for o in d])'
```

**Esperado:** solo `$ORDEN_CLIENTE` (la única con `mecanico_actual_id` igual a
`$MEC_ID`). `$ORDEN_CLIENTE2` queda fuera.
**Status:** ✅ ACCESO RESTRINGIDO A LO ASIGNADO ✅

### TEST 15 — Administrador ve todas

```bash
curl -s $API/ordenes -H "Authorization: Bearer $TOKEN_ADMIN" \
  | python -c 'import sys,json; d=json.load(sys.stdin); print(len(d), [o["orden_id"] for o in d])'
```

**Esperado:** `$ORDEN_CLIENTE` y `$ORDEN_CLIENTE2`.
**Status:** ✅ ACCESO A TODAS ✅

---

## 📊 Matriz de equivalencia

Los 15 tests originales, uno a uno, contra la versión vigente:

| # | Test original (Node, `:3001`) | Versión vigente (Gateway, `:8000`) | Esperado | Cubierto automáticamente por |
|---|---|---|---|---|
| 1 | Cliente → `/auth/users` | Cliente → `POST /ordenes` | `403` | `test_ordenes_api.py::test_post_usuario_no_administrador_recibe_403` |
| 2 | Mecánico → `/auth/users` | Mecánico → `POST /ordenes` | `403` | `test_ordenes_api.py::test_post_usuario_no_administrador_recibe_403` |
| 3 | Admin → `/auth/users` | Admin → `POST /ordenes` | `201` | `test_ordenes_api.py::test_post_administrador_crea_orden_inicial_completa` |
| 4 | Crear órdenes (`descripcion`, `vehiculoId`) | Crear órdenes (`vehiculo_id`) | `201` | `test_ordenes_api.py::test_post_reutiliza_ingreso_abierto` |
| 5 | Cliente → orden ajena | Cliente → `GET /ordenes/{ajena}` | `404` (no `403`) | `test_ordenes_api.py::test_get_detalle_cliente_ajeno_recibe_404` |
| 6 | Cliente → su orden | Cliente → `GET /ordenes/{suya}` | `200` | `test_ordenes_api.py::test_get_detalle_cliente_propietario_accede` |
| 7 | Mecánico → PATCH orden ajena | Mecánico → `GET` no asignada / `PUT .../mecanico` | `404` / `403` | `test_ordenes_api.py::test_get_detalle_mecanico_no_asignado_recibe_404` |
| 8 | Admin → cualquier orden | Admin → `GET /ordenes/{id}` | `200` | `test_ordenes_api.py::test_get_detalle_administrador_accede` |
| 9 | Cliente → `/auth/users/:role` | Cliente → `PUT /ordenes/{id}/mecanico` | `403` | `test_asignacion_ordenes_api.py::test_usuario_sin_rol_administrador_recibe_403` |
| 10 | Admin → `/auth/users/:role` | Admin → `PUT /ordenes/{id}/mecanico` | `200` | `test_asignacion_ordenes_api.py::test_primera_asignacion_cambia_estado_y_registra_ambos_historiales` |
| 11 | Sin token | Sin token en `/auth/me` y `/ordenes` | `401` | `test_ordenes_api.py::test_post_sin_token_devuelve_401` |
| 12 | Token inválido | Token inválido en `/auth/me` | `401` | `test_autorizacion.py::test_token_invalido_devuelve_401` |
| 13 | Cliente ve sus órdenes | `GET /ordenes` como Cliente | `200` filtrado | `test_ordenes_api.py::test_get_cliente_ve_solo_ordenes_de_sus_vehiculos` |
| 14 | Mecánico ve asignadas | `GET /ordenes` como Mecánico | `200` filtrado | `test_ordenes_api.py::test_get_mecanico_ve_solo_ordenes_asignadas` |
| 15 | Admin ve todas | `GET /ordenes` como Admin | `200` completo | `test_ordenes_api.py::test_get_administrador_ve_todas_las_ordenes` |

Refuerzos que no estaban en la versión original y sí existen en la suite actual:

- `test_ordenes_api.py::test_get_detalle_inexistente_devuelve_el_mismo_404`
  comprueba que orden ajena y orden inexistente son indistinguibles.
- `test_vehiculos_api.py::test_get_individual_ajeno_devuelve_el_mismo_404` y
  `test_otro_cliente_no_puede_alterar_el_vehiculo` replican el mismo criterio en
  vehículos.
- `test_asignacion_ordenes_api.py::test_mecanico_anterior_pierde_visibilidad_tras_reasignacion`
  cubre la pérdida de alcance al reasignar.
- `test_jwt.py::test_claims_obligatorios_y_formato` y
  `test_vehiculos_api.py::test_sub_no_entero_devuelve_401` cubren el contrato de
  claims que este documento documenta.

### Casos de la versión original que no tienen equivalente

No se pierden de vista: estos endpoints **no están implementados** y la
documentación de contratos los marca como no publicados
([`docs/contratos-api-gateway.md`](docs/contratos-api-gateway.md), sección
«Contratos todavía no publicados»). Por eso no hay caso ejecutable que los
cubra:

| Endpoint original | Situación |
|---|---|
| `GET /api/auth/users` | No existe. MS1 no expone un listado de usuarios. |
| `GET /api/auth/users/:role` | No existe, por la misma razón. |
| `GET /api/orders/me` | Sustituido por `GET /api/ordenes`, que ya devuelve solo lo visible para el principal. |
| `PATCH /api/orders/:id` | Sustituido por `PUT /api/ordenes/{id}/mecanico`, la única mutación implementada. |

---

## 🔐 Conclusiones de seguridad

1. **Autorización por rol funcionando:** el Administrador opera; Cliente y
   Mecánico reciben `403` en las operaciones que no les corresponden. ✅
2. **Propiedad del recurso funcionando:** un Cliente solo ve los vehículos y las
   órdenes de su perfil; un Mecánico solo las que tiene asignadas. ✅
3. **No enumeración de recursos:** orden ajena y orden inexistente responden el
   mismo `404`, así que la API no revela la existencia de datos de otros. ✅
4. **Autenticación funcionando:** sin token → `401`, token inválido o expirado
   → `401` indistinguible del anterior. ✅
5. **La Gateway no es un punto de confianza para la identidad:** no valida el
   token; cada microservicio lo valida con el contrato común `shared/auth.py`.
   La Gateway no puede falsificar ni filtrar una identidad. ✅
6. **Errores sin enumeración de usuarios:** el login responde `401` con un
   mensaje genérico tanto si el correo no existe como si la contraseña es
   incorrecta. ✅

**VERIFICACIÓN AUTOMÁTICA:** estos 15 casos, más los de vehicles, JWT y
autorización, se ejecutan sin necesidad de servidores levantados con
`pytest` (SQLite en memoria). Ver [`TAREA_8_PRUEBAS_UNITARIAS_INTEGRACION.md`](../TAREA_8_PRUEBAS_UNITARIAS_INTEGRACION.md).

```bash
cd backend
python -m pytest tests -q
```
