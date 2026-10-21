# 🧪 TAREA 8: Pruebas Unitarias y de Integración

**Status:** ✅ COMPLETADA  
**Framework:** pytest + FastAPI TestClient  
**Coverage:** Autenticación, Autorización, JWT, Gateway, Propiedad de Recursos

---

> ⚠️ **Corrección de estado — la versión anterior de este documento afirmaba un
> resultado que no ocurría**
>
> Decía «Framework: Jest + Supertest · Total: 50+ test cases · `npm test` → 50+
> passed». Ejecutando `npm test` en la raíz **ninguna suite llega a cargar**: las
> cinco fallan al resolver sus imports.
>
> ```
> Cannot find module '../../src/utils/jwt.util'   from '__tests__/unit/jwt.test.js'
> Cannot find module '../../src/models/User'      from '__tests__/unit/user.test.js'
> Cannot find module '../../src/index'            from '__tests__/integration/*.test.js'
> ```
>
> La causa es que los tests apuntan a `<raíz>/src/`, pero el código Node está en
> `backend/src/`; y además `src/models/User.js` **no existe en el repositorio**,
> aunque `backend/src/database/users.db.js:1` lo importa. Es decir, el monolito
> Node está incompleto, no solo sus pruebas.
>
> Ese monolito **no es el sistema en ejecución**: la arquitectura vigente son los
> microservicios FastAPI de `backend/services/*` con la Gateway de
> `backend/gateway/`. La cobertura que esta tarea pide **sí existe**, pero en
> Python y con otra escala. A partir de aquí el documento describe la suite real;
> al final se conserva el inventario de la suite Jest como registro histórico.

---

## 📋 RESUMEN

La suite vigente cubre, con **1113 pruebas** en 54 archivos:

- ✅ Autenticación (registro, login, `/auth/me`, intentos fallidos, historial de roles)
- ✅ JWT: firma, expiración, claims obligatorios, formato de `sub` y `roles`, integridad del token
- ✅ Autorización por rol, incluidos multirol, `401` vs `403` y normalización
- ✅ Propiedad de recursos y acceso cruzado, con `404` indistinguible
- ✅ Acceso indebido entre roles y recursos ajenos del mismo rol
- ✅ Autenticación por canales web y móvil
- ✅ API Gateway: enrutamiento, formato de errores, OpenAPI, CORS, evidencias, health
- ✅ Integración real del JWT emitido por MS1 validado en MS2 a través de la Gateway
- ✅ Contratos de MS3 (presupuestos, aislamiento, persistencia) y MS4 (evidencias, ciclo de archivos, huérfanos)
- ✅ Decisiones de presupuesto (integración y migraciones)

**Total:** 1113 pruebas → **1054 pasan, 55 se omiten y 4 son `xfail` estricto**
(que registran huecos de seguridad abiertos; ver la sección «Casos pendientes»).
Las omitidas son las que requieren un servicio externo levantado (MinIO o
PostgreSQL descartable) y se habilitan siguiendo la sección «Cómo ejecutar».

Además de `pytest`, el repositorio tiene **dos suites más** que también se
ejecutan hoy:

| Suite | Comando | Resultado verificado |
|---|---|---|
| Frontend (vitest) | `cd frontend && npm test` | **175 pruebas en 37 archivos**, todas pasan |
| Humo Gateway → MS1 | `cd backend && python scripts/prueba_comunicacion_smoke.py` | **33 comprobaciones**, salida 0, con la Gateway y MS1 levantados |

La de frontend cubre los componentes de UI; la de humo comprueba sobre HTTP real
que la cadena de autenticación responde, con casos válidos y rechazados, y es el
equivalente ejecutable de la parte de autenticación de TAREA 7. Ninguna de las
dos sustituye a `pytest`.

---

## 📁 ESTRUCTURA DE PRUEBAS

### Suite vigente (pytest)

```
backend/
├── tests/
│   ├── conftest.py                    Fixtures: SQLite en memoria, .env de pruebas
│   ├── test_acceso_indebido_roles.py               (10)  Acceso indebido entre roles (4 xfail)
│   ├── test_acceso_recursos_ajenos_mismo_rol.py    (8)  Recursos ajenos del mismo rol
│   ├── test_asignacion_ordenes_api.py              (24)  Asignación, reasignación, idempotencia
│   ├── test_autenticacion_canales.py               (10)  Autenticación por canales web/móvil
│   ├── test_auth_api.py                            (8)  Registro, login, /auth/me
│   ├── test_autorizacion.py                        (6)  401 vs 403, multirol
│   ├── test_decisiones_presupuesto_integracion.py  (28)  Decisiones de presupuesto
│   ├── test_decisiones_presupuesto_postgresql.py   (45)  Decisiones en PostgreSQL (se omiten sin PG)
│   ├── test_gateway_errores_proxy.py               (28)  Errores del proxy
│   ├── test_gateway_estructura.py                  (6)  Estructura de la Gateway
│   ├── test_gateway_evidencias.py                  (14)  Límites de la ruta de evidencias
│   ├── test_gateway_formato.py                     (15)  Formato común de errores
│   ├── test_gateway_health_servicios.py            (10)  Health de servicios
│   ├── test_gateway_openapi.py                     (42)  Swagger y esquemas
│   ├── test_gateway_openapi_ejemplos.py            (20)  Ejemplos del OpenAPI
│   ├── test_gateway_openapi_evidencias.py          (4)  OpenAPI de evidencias
│   ├── test_gateway_rechazos_evidencias.py         (25)  Rechazos de evidencias
│   ├── test_gateway_rutas.py                       (43)  Enrutamiento y reenvío
│   ├── test_historial_roles.py                     (6)  Historial de roles
│   ├── test_integracion_jwt_gateway_ms2.py         (5)  JWT real MS1→Gateway→MS2
│   ├── test_integracion_prefijos.py                (21)  Prefijos de enrutamiento
│   ├── test_integridad_token_jwt.py                (12)  Integridad del token JWT
│   ├── test_jwt.py                                 (11)  Claims, firma, expiración
│   ├── test_login_intentos_fallidos.py             (2)  Intentos fallidos de login
│   ├── test_migraciones_decisiones.py              (2)  Migraciones de decisiones
│   ├── test_ms2_integracion_ms3.py                 (12)  Integración MS2 → MS3
│   ├── test_ms3_aislamiento.py                     (20)  Aislamiento de MS3
│   ├── test_ms3_estructura.py                      (12)  Estructura de MS3
│   ├── test_ms3_integracion_ms2.py                 (17)  Integración MS3 → MS2
│   ├── test_ms3_persistencia_base.py               (15)  Persistencia de MS3
│   ├── test_ms3_presupuestos_contratos.py          (15)  Contratos de presupuestos
│   ├── test_ms4_api_evidencias.py                  (20)  API de evidencias
│   ├── test_ms4_asociacion_ordenes.py              (38)  Asociación de evidencias con órdenes
│   ├── test_ms4_autorizacion_evidencias.py         (24)  Autorización de evidencias
│   ├── test_ms4_ciclo_archivos.py                  (12)  Ciclo de archivos (6 se omiten sin MinIO)
│   ├── test_ms4_config.py                          (2)  Configuración de MS4
│   ├── test_ms4_convencion_metadatos.py            (19)  Convención de metadatos
│   ├── test_ms4_errores_carga.py                   (12)  Errores de carga
│   ├── test_ms4_estructura.py                      (6)  Estructura de MS4
│   ├── test_ms4_huerfanos.py                       (23)  Evidencias huérfanas (1 se omite sin MinIO)
│   ├── test_ms4_limites_archivos.py                (49)  Límites de tamaño y cantidad
│   ├── test_ms4_logs.py                            (23)  Logs de evidencias
│   ├── test_ms4_minio_integracion.py               (2)  Integración MinIO (se omite sin MinIO)
│   ├── test_ms4_modelo_evidencia.py                (17)  Modelo de evidencia
│   ├── test_ms4_recepcion.py                       (18)  Recepción de evidencias
│   ├── test_ms4_recepcion_minio.py                 (1)  Recepción MinIO (se omite sin MinIO)
│   ├── test_ms4_url_firmada.py                     (17)  URLs firmadas
│   ├── test_ms4_validacion_contenido.py            (43)  Validación de contenido
│   ├── test_normalizacion_401_403.py               (14)  Normalización de 401 vs 403
│   ├── test_ordenes_api.py                         (142)  Visibilidad y creación de órdenes
│   ├── test_seguridad_autenticacion.py             (12)  Seguridad de autenticación
│   ├── test_usuarios_roles.py                      (43)  Usuarios y roles
│   ├── test_validadores_orden.py                   (22)  Validadores de dominio
│   └── test_vehiculos_api.py                       (58)  Propiedad y CRUD de vehículos
│
├── requirements-dev.txt               pytest, httpx, respx
└── verificar_conexion.py              Conexiones a las 4 bases de datos
```

`tests/conftest.py` fija las variables `MS*_JWT_SECRET_KEY` y `MS*_DATABASE_URL`
por defecto, así que la suite corre sin `.env` y sin PostgreSQL. 55 pruebas se
omiten si no hay servicios externos: 10 de MinIO
(`docker compose up -d minio minio_init`) y 45 de PostgreSQL descartable; ver
la sección «Casos pendientes».

### Suite histórica (Jest) — no ejecutable

Se conserva el inventario original como registro. **No se ejecuta** y no debe
usarse como evidencia de cobertura; ver el aviso de la cabecera.

```
backend/
├── __tests__/
│   ├── unit/
│   │   ├── jwt.test.js              (9 tests)
│   │   └── user.test.js             (10 tests)
│   │
│   └── integration/
│       ├── auth.integration.test.js  (15 tests)
│       ├── authorization.integration.test.js (11 tests)
│       └── ownership.integration.test.js (13 tests)
│
├── jest.config.js                   (Configuración)
└── package.json                     (Scripts de test)
```

---

## 🧪 PRUEBAS UNITARIAS

### 1. JWT Utils (`__tests__/unit/jwt.test.js`)

**9 tests:**

```javascript
✅ Generate token with correct payload
✅ Verify valid token
✅ Reject invalid token
✅ Extract token from Authorization header
✅ Reject header without Bearer prefix
✅ Reject missing Authorization header
✅ Decode token without verification
✅ Token contains expiration claim
```

**Qué prueba:**
- Generación correcta de JWT
- Verificación de tokens válidos/inválidos
- Extracción de headers Authorization
- Claims correctos (id, email, role, exp)

---

### 2. User Model (`__tests__/unit/user.test.js`)

**10 tests:**

```javascript
✅ Validate correct email format
✅ Reject invalid email format
✅ Validate password with requirements
✅ Reject password too short
✅ Reject password without uppercase
✅ Reject password without number
✅ Hash password correctly
✅ Compare passwords correctly
✅ Reject wrong password
✅ User toJSON does not include password
```

**Qué prueba:**
- Validación de email (regex)
- Validación de password (8+, mayús, número)
- Bcryptjs hashing funciona
- Comparación segura de contraseñas
- No expone passwordHash en JSON

---

## 🔗 PRUEBAS DE INTEGRACIÓN

### 1. Authentication Endpoints (`auth.integration.test.js`)

**15 tests:**

```javascript
✅ POST /api/auth/register - Register new user (201)
✅ POST /api/auth/register - Reject invalid email (400)
✅ POST /api/auth/register - Reject weak password (400)
✅ POST /api/auth/register - Reject duplicate email (400)
✅ POST /api/auth/login - Login successfully (200)
✅ POST /api/auth/login - Reject wrong password (401)
✅ POST /api/auth/login - Generic error for non-existent (401)
✅ GET /api/auth/profile - Get with valid token (200)
✅ GET /api/auth/profile - Reject missing token (401)
✅ GET /api/auth/profile - Reject invalid token (401)
✅ GET /api/auth/verify - Verify valid token (200)
```

**Qué prueba:**
- Registro funciona correctamente
- Validaciones se ejecutan
- Login con credenciales correctas
- Errores genéricos (no revela qué falla)
- Acceso a rutas protegidas requiere token válido

---

### 2. Authorization by Roles (`authorization.integration.test.js`)

**11 tests:**

```javascript
✅ Admin can access /users (200)
✅ Cliente cannot access /users (403)
✅ Mecánico cannot access /users (403)

✅ Admin can access /users/:role (200)
✅ Cliente cannot access /users/:role (403)
✅ Mecánico cannot access /users/:role (403)

✅ Reject request without token (401)
✅ Reject request with invalid token (401)

✅ All roles can access /profile (200)
```

**Qué prueba:**
- Roles tienen permisos correctos
- Admin solo accede a /users
- Cliente/Mecánico no pueden listar usuarios
- Token requerido en rutas protegidas
- Middleware de autorización funciona

---

### 3. Resource Ownership (`ownership.integration.test.js`)

**13 tests:**

```javascript
✅ Cliente can access their own order (200)
✅ Cliente cannot access another's order (403)

✅ Cliente sees only their orders
✅ Admin can access any order (200)
✅ Admin can see all orders (200)

✅ Mecánico cannot access unassigned order (403)

✅ Cliente cannot update other's order (403)
✅ Mecánico cannot update unassigned (403)
✅ Admin can update any order (200)
```

**Qué prueba:**
- Verificación de propiedad funciona
- Cliente solo ve sus órdenes
- Admin accede a todo sin restricción
- Prevención de acceso cruzado
- PATCH solo por propietario o admin

---

## 🚀 CÓMO EJECUTAR LAS PRUEBAS

### Instalar dependencias

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

En Linux/macOS: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt`

### Ejecutar todas las pruebas
```bash
python -m pytest tests -q
```

### Resultado verificado
```
1054 passed, 55 skipped, 4 xfailed, 51 warnings in 295.78s (0:04:55)
```

De las 1113 pruebas, **55 se omiten** por depender de un servicio externo no
levantado y **4 son `xfail` estricto** (huecos de seguridad registrados, no
fallos). El desglose completo está en la sección
[«Casos pendientes»](#-casos-pendientes).

Las omitidas se describen solas con `-rs` y son de dos grupos:

```
SKIPPED tests/test_ms4_ciclo_archivos.py:389: MinIO no está disponible
        (docker compose up -d minio minio_init)      ← 10 omitidas de MinIO (una de test_ms4_huerfanos.py)
SKIPPED tests/test_decisiones_presupuesto_postgresql.py:92:
        Se requieren dos PostgreSQL locales descartables para SCRUM-397/438
                                                      ← 45 omitidas de PostgreSQL
```

Para incluirlas:
```bash
docker compose up -d minio minio_init        # habilita las 10 de MinIO
python -m pytest tests -q
```

Las 45 de PostgreSQL necesitan además dos bases descartables levantadas; ver
`test_decisiones_presupuesto_postgresql.py`.

### Ejecutar un subconjunto
```bash
python -m pytest tests/test_autorizacion.py -v
python -m pytest tests -k "gateway or jwt" -q
```

### Comprobar las conexiones a las bases de datos
```bash
python verificar_conexion.py     # requiere los 4 servicios de DB levantados
```

---

## 📊 COBERTURA

**Módulos del sistema en ejecución con cobertura directa:**

| Módulo | Archivo(s) de pruebas | Pruebas |
|---|---|---|
| `shared/auth.py` — emisión y validación de JWT | `test_jwt.py` (11), `test_integridad_token_jwt.py` (12) | 23 |
| `services/ms1_auth` — registro, login, `/auth/me`, roles, seguridad, canales web/móvil | `test_auth_api.py` (8), `test_autorizacion.py` (6), `test_usuarios_roles.py` (43), `test_historial_roles.py` (6), `test_login_intentos_fallidos.py` (2), `test_autenticacion_canales.py` (10), `test_normalizacion_401_403.py` (14), `test_seguridad_autenticacion.py` (12) | 101 |
| `services/ms2_taller` — vehículos | `test_vehiculos_api.py` | 58 |
| `services/ms2_taller` — órdenes y asignación de mecánico | `test_ordenes_api.py` (142), `test_asignacion_ordenes_api.py` (24) | 166 |
| `services/ms2_taller` — validadores de dominio | `test_validadores_orden.py` | 22 |
| `gateway` — rutas, formato de errores, OpenAPI, CORS, evidencias, health | `test_gateway_rutas.py` (43), `test_gateway_errores_proxy.py` (28), `test_gateway_openapi.py` (42), `test_gateway_openapi_ejemplos.py` (20), `test_gateway_openapi_evidencias.py` (4), `test_gateway_formato.py` (15), `test_gateway_rechazos_evidencias.py` (25), `test_gateway_evidencias.py` (14), `test_gateway_health_servicios.py` (10), `test_gateway_estructura.py` (6) | 207 |
| Integración MS1 → Gateway → MS2 y prefijos | `test_integracion_jwt_gateway_ms2.py` (5), `test_integracion_prefijos.py` (21) | 26 |
| `services/ms3_presupuestos` | `test_ms3_aislamiento.py` (20), `test_ms3_integracion_ms2.py` (17), `test_ms3_presupuestos_contratos.py` (15), `test_ms3_persistencia_base.py` (15), `test_ms3_estructura.py` (12), `test_ms2_integracion_ms3.py` (12) | 91 |
| `services/ms3_presupuestos` — decisiones de presupuesto | `test_decisiones_presupuesto_integracion.py` (28), `test_decisiones_presupuesto_postgresql.py` (45, se omiten sin PostgreSQL), `test_migraciones_decisiones.py` (2) | 75 |
| `services/ms4_evidencias` | `test_ms4_validacion_contenido.py` (43), `test_ms4_limites_archivos.py` (49), `test_ms4_asociacion_ordenes.py` (38), `test_ms4_autorizacion_evidencias.py` (24), `test_ms4_huerfanos.py` (23, 1 se omite sin MinIO), `test_ms4_logs.py` (23), `test_ms4_api_evidencias.py` (20), `test_ms4_convencion_metadatos.py` (19), `test_ms4_recepcion.py` (18), `test_ms4_modelo_evidencia.py` (17), `test_ms4_url_firmada.py` (17), `test_ms4_ciclo_archivos.py` (12, 6 se omiten sin MinIO), `test_ms4_errores_carga.py` (12), `test_ms4_estructura.py` (6), `test_ms4_config.py` (2), `test_ms4_minio_integracion.py` (2, se omiten sin MinIO), `test_ms4_recepcion_minio.py` (1, se omite sin MinIO) | 326 |
| Seguridad transversal — acceso indebido entre roles y recursos ajenos del mismo rol | `test_acceso_indebido_roles.py` (10, 4 `xfail` estricto), `test_acceso_recursos_ajenos_mismo_rol.py` (8) | 18 |
| **Total** | **54 archivos** | **1113** |

**Total de la suite: 1113 pruebas** → 1054 pasan, 55 se omiten (10 de MinIO y 45
de PostgreSQL descartable) y 4 son `xfail` estricto (huecos de seguridad
registrados en la sección «Casos pendientes»).

**Cobertura transversal de seguridad**, presente en varios archivos:

- `401` vs `403`: token ausente, inválido, expirado y `sub` no entero devuelven
  `401`; el rol insuficiente devuelve `403`.
- `404` indistinguible: un recurso ajeno y uno inexistente responden igual, tanto
  en órdenes como en vehículos.
- Campos controlados por el servidor: el body no puede fijar propietario,
  estado, responsable ni fechas.
- Rollback: los fallos de persistencia no dejan escrituras parciales.
- Idempotencia: repetir la misma asignación no crea historial duplicado.

No se publica un porcentaje de cobertura de líneas: la suite no se ejecuta con
`--cov`, así que cualquier cifra en este documento estaría sin respaldo. Para
obtenerla:

```bash
python -m pip install pytest-cov
python -m pytest tests --cov=services --cov=gateway --cov=shared
```

### Cobertura de la suite histórica (no vigente)

Se lista solo como registro de lo que la suite Jest pretendía cubrir; varios de
esos archivos no existen en el repositorio.

- `jwt.util.js` · `models/User.js` — **no existen**
- `middleware/auth.middleware.js`, `middleware/ownership.middleware.js`,
  `controllers/auth.controller.js`, `controllers/orders.controller.js`,
  `routes/auth.routes.js`, `routes/orders.routes.js` — existen en
  `backend/src/`, pero el módulo `models/User` del que dependen no

---

## 🔍 EJEMPLOS DE PRUEBAS (suite vigente)

### Ejemplo 1: contrato de claims del JWT
```python
def test_claims_obligatorios_y_formato(sin_exp, sin_sub, sub_uuid):
    """El token exige sub entero positivo y roles no vacía."""
```

### Ejemplo 2: el rol insuficiente no es lo mismo que un token inválido
```python
def test_mecanico_sin_cliente_recibe_403(...):
    """Token válido pero rol insuficiente -> 403, no 401."""
```

### Ejemplo 3: un recurso ajeno es indistinguible de uno inexistente
```python
def test_get_detalle_cliente_ajeno_recibe_404(...):
    """No se revela la existencia de órdenes de otro cliente."""
```

---

## 🔍 EJEMPLOS DE PRUEBAS (suite histórica, Jest)

### Ejemplo 1: JWT Generation
```javascript
test('Generate token with correct payload', () => {
  const payload = { id: 'usr_123', email: 'test@test.cl', role: 'cliente' };
  const token = JWTUtil.generateToken(payload);
  
  expect(token).toBeTruthy();
  expect(token.split('.').length).toBe(3); // JWT = header.payload.signature
});
```

### Ejemplo 2: Password Validation
```javascript
test('Reject password without uppercase', () => {
  const noUppercase = 'password@123';
  const result = User.validatePassword(noUppercase);
  
  expect(result.valid).toBe(false);
  expect(result.message).toContain('mayúscula');
});
```

### Ejemplo 3: Authorization
```javascript
test('Admin can access /users', async () => {
  const res = await request(app)
    .get('/api/auth/users')
    .set('Authorization', `Bearer ${adminToken}`);

  expect(res.statusCode).toBe(200);
  expect(res.body.users).toBeDefined();
});

test('Cliente cannot access /users', async () => {
  const res = await request(app)
    .get('/api/auth/users')
    .set('Authorization', `Bearer ${clienteToken}`);

  expect(res.statusCode).toBe(403);
  expect(res.body.error).toContain('Acceso denegado');
});
```

### Ejemplo 4: Resource Ownership
```javascript
test('Cliente cannot access another clients order', async () => {
  const res = await request(app)
    .get(`/api/orders/${orden1Id}`)
    .set('Authorization', `Bearer ${cliente2Token}`);

  expect(res.statusCode).toBe(403);
  expect(res.body.error).toContain('No tienes permiso');
});
```

---

## ✅ RESULTADOS ESPERADOS

### Suite vigente — resultado verificado

```
1054 passed, 55 skipped, 4 xfailed, 51 warnings in 295.78s (0:04:55)
```

Reproducir con `cd backend && python -m pytest tests -q`. De las 1113 pruebas,
55 se omiten por depender de servicios externos (10 de MinIO y 45 de PostgreSQL
descartable) y 4 son `xfail` estricto por huecos de seguridad abiertos; el
detalle está en la sección «Casos pendientes».

### Suite histórica (Jest) — resultado real

La salida que sigue **no** es la de este repositorio. `npm test` falla al
cargar las cinco suites, por lo que estas líneas no deben usarse como evidencia
de cobertura:

```

```
 PASS  __tests__/unit/jwt.test.js (150ms)
  JWTUtil - JWT Generation and Verification
    ✓ Generate token with correct payload (5ms)
    ✓ Verify valid token (3ms)
    ✓ Reject invalid token (2ms)
    ✓ Extract token from Authorization header (2ms)
    ✓ Reject header without Bearer prefix (2ms)
    ✓ Reject missing Authorization header (2ms)
    ✓ Decode token without verification (2ms)
    ✓ Token contains expiration claim (2ms)
    ✓ Token has correct structure (2ms)

 PASS  __tests__/unit/user.test.js (250ms)
  User Model - Validation and Hashing
    ✓ Validate correct email format (2ms)
    ✓ Reject invalid email format (3ms)
    ✓ Validate password with correct requirements (2ms)
    ✓ Reject password too short (2ms)
    ✓ Reject password without uppercase (2ms)
    ✓ Reject password without number (2ms)
    ✓ Hash password correctly (75ms)
    ✓ Compare passwords correctly (85ms)
    ✓ Reject wrong password (80ms)
    ✓ User toJSON does not include password (2ms)

 PASS  __tests__/integration/auth.integration.test.js (450ms)
  Authentication Endpoints Integration
    ✓ POST /api/auth/register - Register new user (120ms)
    ✓ POST /api/auth/register - Reject invalid email (30ms)
    ✓ POST /api/auth/register - Reject weak password (30ms)
    ✓ POST /api/auth/register - Reject duplicate email (100ms)
    ✓ POST /api/auth/login - Login successfully (110ms)
    ✓ POST /api/auth/login - Reject wrong password (80ms)
    ✓ POST /api/auth/login - Generic error for non-existent user (80ms)
    ✓ GET /api/auth/profile - Get user profile with valid token (100ms)
    ✓ GET /api/auth/profile - Reject missing token (20ms)
    ✓ GET /api/auth/profile - Reject invalid token (20ms)
    ✓ GET /api/auth/verify - Verify valid token (100ms)

Tests:       50+ passed, 0 failed
Snapshots:   0 total
Time:        1.234s
```

---

## ⏳ CASOS PENDIENTES

De las 1113 pruebas de la suite vigente, **1054 pasan**. Las restantes **59 no
son fallos**: 55 se omiten por depender de un servicio externo no levantado y 4
están marcadas `xfail` estricto porque registran un hueco de seguridad abierto.
Este documento las deja todas identificadas; ninguna se esconde ni se
«bendice».

### 1. Omitidas por servicio externo (55)

Se habilitan levantando el servicio correspondiente y volviendo a correr la
suite. Con todos los servicios levantadas no debería quedar ninguna omitida.

| Grupo | Pruebas | Servicio requerido | Cómo habilitarla |
|---|---|---|---|
| `test_ms4_ciclo_archivos.py` | 6 | MinIO | `docker compose up -d minio minio_init` |
| `test_ms4_minio_integracion.py` | 2 | MinIO | ídem |
| `test_ms4_recepcion_minio.py` | 1 | MinIO | ídem |
| `test_ms4_huerfanos.py` | 1 | MinIO | ídem (reutiliza el fixture `cliente_minio` de `test_ms4_recepcion_minio.py`) |
| `test_decisiones_presupuesto_postgresql.py` | 45 | Dos PostgreSQL locales descartables | Ver el propio archivo (casos SCRUM-397/438) |
| **Total** | **55** | **MinIO (10) + PostgreSQL (45)** | |

### 2. `xfail` estrictos por hueco de seguridad abierto (4)

Son en `test_acceso_indebido_roles.py`. Marcan un comportamiento **no deseado y
conocido**: hoy la API lo permite y la prueba lo documenta como brecha. Son
**estrictos** (`strict=True`): si alguien corrige la brecha, la prueba empieza a
fallar y obliga a retirar la marca, así nadie la deja pasar por alto.

| Prueba | Brecha que registra |
|---|---|
| `test_mecanico_no_asignado_no_crea_presupuesto_de_orden_ajena` | Un mecánico crea presupuesto sobre una orden que no tiene asignada (§4.4 de la matriz) |
| `test_mecanico_no_crea_presupuesto_de_orden_inexistente` | Variante del §4.4 usando una orden inexistente |
| `test_administrador_no_asigna_a_un_usuario_inexistente` | `mecanico_id` de la orden sin validar contra MS1 (§4.3 de la matriz) |
| `test_administrador_no_asigna_a_un_usuario_sin_rol_mecanico` | Variante del §4.3: el id existe pero no tiene rol mecánico |

Referencia completa de huecos y decisiones pendientes:
[`docs/matriz-autorizacion-roles.md`](backend/docs/matriz-autorizacion-roles.md).

### 3. No automatizado en esta suite

- **Frontend (vitest):** se corre aparte (`cd frontend && npm test`), 175 pruebas
  en 37 archivos. No la sustituye `pytest`.
- **Humo sobre HTTP real:** `scripts/prueba_comunicacion_smoke.py`, 33
  comprobaciones, requiere la Gateway y MS1 levantadas. No corre dentro de
  `pytest`.

### 4. Suite histórica (Jest) no ejecutable

`__tests__/`, `jest.config.js` y `package.json` de la raíz no cargan ninguna
suite y `backend/src/` está incompleto (`models/User` ausente). Queda **pendiente
de decisión del equipo** retirarla; ver la sección «Conclusión». No se ha tocado
ningún archivo de esa suite en este registro.

---

## 🛠️ CONFIGURACIÓN

### Suite vigente

No requiere archivo de configuración: `pytest` descubre `tests/` por convención
y `tests/conftest.py` fija las variables de entorno de pruebas. Las dependencias
de prueba se instalan con `requirements-dev.txt` (`pytest`, `httpx`, `respx`).

### Suite histórica (jest.config.js) — no vigente

```javascript
module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.test.js'],
  collectCoverageFrom: [
    'src/**/*.js',      // ← ruta inexistente: el código Node está en backend/src/
    '!src/index.js'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'html'],
  testTimeout: 10000,
  verbose: true
};
```

Los tres caminos que fallan —`src/**/*.js`, `main: "src/index.js"` en
`package.json` y los `require('../../src/...')` de `__tests__/`— apuntan a
`<raíz>/src/`, que no existe. Por eso la suite histórica no arranca.

---

## 📈 BENEFICIOS

✅ **Confianza:** Sabe que el código funciona  
✅ **Refactoring seguro:** Puede cambiar código sin miedo  
✅ **Documentación viva:** Las pruebas documentan el comportamiento  
✅ **Catch bugs:** Previene regressions  
✅ **Quality:** 1113 pruebas de uso cubiertas, incluidas las de seguridad

---

## 🎯 CONCLUSIÓN

**Pruebas completas y verificadas sobre el sistema en ejecución:**
- 1113 pruebas: 1054 pasan, 55 se omiten por servicios externos (10 MinIO y 45 PostgreSQL descartable), 4 son `xfail` estricto por huecos de seguridad abiertos, 0 fallos
- Autenticación verificada
- Autorización verificada, con `401` y `403` diferenciados
- Propiedad de recursos y acceso cruzado verificados, con `404` indistinguible
- Contrato de claims del JWT verificado contra `shared/auth.py`
- Gateway verificada: enrutamiento, reenvío de `Authorization`, errores, OpenAPI
- Integración real JWT de MS1 → Gateway → MS2 verificada

**Pendiente de decisión del equipo:** la suite Jest de la raíz
(`__tests__/`, `jest.config.js`, `package.json`) no es ejecutable y su código
(`backend/src/`) está incompleto por el `models/User` ausente. Recomiendo
retirarla cuando el sistema FastAPI sea el único vigente, pero **no se ha
tocado ningún archivo de esa suite** en este cambio: es una decisión del equipo,
no una corrección silenciosa.

**TAREA 8: COMPLETADA** ✅

