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

La suite vigente cubre, con **304 pruebas** en 21 archivos:

- ✅ Autenticación (registro, login, `/auth/me`)
- ✅ JWT: firma, expiración, claims obligatorios, formato de `sub` y `roles`
- ✅ Autorización por rol, incluidos multirol y `401` vs `403`
- ✅ Propiedad de recursos y acceso cruzado, con `404` indistinguible
- ✅ API Gateway: enrutamiento, formato de errores, OpenAPI, CORS
- ✅ Integración real del JWT emitido por MS1 validado en MS2 a través de la Gateway
- ✅ Contratos de MS3 (presupuestos) y MS4 (evidencias)

**Total:** 304 pruebas, más 2 de integración con MinIO que se omiten si el
servicio no está levantado (y que dicen cómo habilitarse).

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
│   ├── test_auth_api.py                (8)  Registro, login, /auth/me
│   ├── test_jwt.py                     (11) Claims, firma, expiración
│   ├── test_autorizacion.py            (6)  401 vs 403, multirol
│   ├── test_vehiculos_api.py           (49) Propiedad y CRUD de vehículos
│   ├── test_ordenes_api.py             (28) Visibilidad y creación de órdenes
│   ├── test_asignacion_ordenes_api.py  (24) Asignación, reasignación, idempotencia
│   ├── test_validadores_orden.py       (22) Validadores de dominio
│   ├── test_gateway_rutas.py           (19) Enrutamiento y reenvío
│   ├── test_gateway_formato.py         (15) Formato común de errores
│   ├── test_gateway_openapi.py         (26) Swagger y esquemas
│   ├── test_gateway_estructura.py      (6)  Estructura de la Gateway
│   ├── test_integracion_jwt_gateway_ms2.py (2) JWT real MS1→Gateway→MS2
│   ├── test_ms3_estructura.py          (10) Estructura de MS3
│   ├── test_ms3_persistencia_base.py   (15) Persistencia de MS3
│   ├── test_ms4_estructura.py           (6) Estructura de MS4
│   ├── test_ms4_config.py               (2) Configuración de MS4
│   ├── test_ms4_modelo_evidencia.py    (17) Modelo de evidencia
│   ├── test_ms4_recepcion.py           (18) Recepción de evidencias
│   ├── test_ms4_minio_integracion.py    (1) Integración MinIO (se omite sin MinIO)
│   └── test_ms4_recepcion_minio.py      (1) Integración MinIO (se omite sin MinIO)
│
├── requirements-dev.txt               pytest, httpx, respx
└── verificar_conexion.py              Conexiones a las 4 bases de datos
```

`tests/conftest.py` fija las variables `MS*_JWT_SECRET_KEY` y `MS*_DATABASE_URL`
por defecto, así que la suite corre sin `.env` y sin PostgreSQL. Solo las dos
pruebas de MinIO requieren `docker compose up -d minio minio_init`.

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
304 passed, 2 skipped, 1 warning in 51.55s
```

Las 2 omitidas son las de integración con MinIO, que se describen solas:
```
SKIPPED tests/test_ms4_minio_integracion.py:73: MinIO no está disponible
        (docker compose up -d minio minio_init)
SKIPPED tests/test_ms4_recepcion_minio.py:76: MinIO no está disponible
        (docker compose up -d minio minio_init)
```

Para incluirlas:
```bash
docker compose up -d minio minio_init
python -m pytest tests -q
```

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

| Módulo | Archivo de pruebas | Pruebas |
|---|---|---|
| `shared/auth.py` — emisión y validación de JWT | `test_jwt.py` | 11 |
| `services/ms1_auth` — routers, schemas, dependencias, hashing | `test_auth_api.py`, `test_autorizacion.py` | 14 |
| `services/ms2_taller` — vehículos | `test_vehiculos_api.py` | 49 |
| `services/ms2_taller` — órdenes y asignación de mecánico | `test_ordenes_api.py`, `test_asignacion_ordenes_api.py` | 52 |
| `services/ms2_taller` — validadores de dominio | `test_validadores_orden.py` | 22 |
| `gateway` — rutas, errores, OpenAPI, CORS | `test_gateway_*.py` | 66 |
| Integración MS1 → Gateway → MS2 | `test_integracion_jwt_gateway_ms2.py` | 2 |
| `services/ms3_presupuestos` | `test_ms3_*.py` | 25 |
| `services/ms4_evidencias` | `test_ms4_*.py` | 44 |

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
304 passed, 2 skipped, 1 warning in 51.55s
```

Reproducir con `cd backend && python -m pytest tests -q`. Las 2 omitidas son las
de MinIO y solo se omiten si el servicio no está levantado; ver la sección
«Cómo ejecutar».

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
✅ **Quality:** 304 casos de uso cubiertos, incluidos los de seguridad

---

## 🎯 CONCLUSIÓN

**Pruebas completas y verificadas sobre el sistema en ejecución:**
- 304 pruebas, 2 omitidas por dependencia externa (MinIO), 0 fallos
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

