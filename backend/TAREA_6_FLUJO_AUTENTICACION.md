# 🔐 DOCUMENTACIÓN: Flujo de Autenticación, Claims y Autorización

**TAREA 6 - Semana 2**

---

## 1. FLUJO COMPLETO: REGISTRO → LOGIN → ACCESO A RECURSO

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENTE (Frontend)                        │
└─────────────────────────────────────────────────────────────┘
         │
         │ 1. POST /api/auth/register
         │    { email, password, name, role: "cliente" }
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              SERVIDOR - CONTROLADOR REGISTER                 │
│                                                              │
│  1. Valida email (regex)                                     │
│  2. Valida password (8+, mayús, número)                     │
│  3. Verifica que no existe                                   │
│  4. Hashea password con bcryptjs                            │
│  5. Guarda en BD                                             │
│                                                              │
│  Datos guardados:                                            │
│  {                                                           │
│    id: "usr_169...",                                         │
│    email: "cliente@x.cl",                                    │
│    passwordHash: "$2b$10$...",  ← NUNCA retorna esto        │
│    name: "Juan",                                             │
│    role: "cliente",             ← CLAIM importante           │
│    isActive: true                                            │
│  }                                                           │
│                                                              │
│  6. Genera JWT con CLAIMS                                    │
│     jwt.sign({                                               │
│       id: "usr_169...",                                      │
│       email: "cliente@x.cl",                                 │
│       role: "cliente"             ← CLAIM en token          │
│     }, SECRET, { expiresIn: "24h" })                         │
│                                                              │
│     Resultado: eyJhbGciOiJIUzI1NiIs...                       │
│                                                              │
│  7. Retorna 201 + token                                      │
└─────────────────────────────────────────────────────────────┘
         │
         │ Respuesta: { user, token }
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              CLIENTE - Guarda token                          │
│                                                              │
│  localStorage.setItem('auth_token', token)                  │
│                                                              │
│  Decodificando el token (sin verificar):                    │
│  {                                                           │
│    "iat": 1694800000,                                        │
│    "exp": 1694886400,     ← Expira en 24 horas             │
│    "id": "usr_169...",     ← CLAIM                          │
│    "email": "cliente@x.cl", ← CLAIM                         │
│    "role": "cliente"        ← CLAIM CRUCIAL para autorización│
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
         │
         │ (Tiempo después)
         │ 2. POST /api/auth/login
         │    { email, password }
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              SERVIDOR - CONTROLADOR LOGIN                    │
│                                                              │
│  1. Busca usuario por email                                  │
│  2. Si no existe → 401 "Credenciales inválidas"             │
│  3. Si existe: bcrypt.compare(password, hash)               │
│     - Si no coincide → 401 "Credenciales inválidas"         │
│     - Si coincide → continúa                                │
│  4. Genera JWT IGUAL con mismo payload                       │
│  5. Retorna 200 + token                                      │
└─────────────────────────────────────────────────────────────┘
         │
         │ Respuesta: { user, token }
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│         CLIENTE - Guarda token en localStorage              │
│         Todas las próximas requests llevan:                  │
│         Authorization: Bearer eyJhbGciOi...                 │
└─────────────────────────────────────────────────────────────┘
         │
         │ 3. GET /api/orders/me
         │    Header: Authorization: Bearer <token>
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│         SERVIDOR - MIDDLEWARE authMiddleware                 │
│                                                              │
│  1. Extrae token del header Authorization                   │
│  2. jwt.verify(token, SECRET)                               │
│     - Si inválido → 401 "Token inválido"                    │
│     - Si expirado → 401 "Token expirado"                    │
│     - Si válido → decodifica                                │
│                                                              │
│  3. Obtiene los CLAIMS:                                      │
│     req.user = {                                             │
│       id: "usr_169...",                                      │
│       email: "cliente@x.cl",                                 │
│       role: "cliente"    ← CRUCIAL para autorización        │
│     }                                                        │
│                                                              │
│  4. Llama next()                                             │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│    SERVIDOR - MIDDLEWARE requireRole(['cliente'])            │
│                                                              │
│  1. ¿req.user existe? SÍ                                    │
│  2. ¿req.user.role está en ['cliente']? SÍ                 │
│  3. Llama next()                                             │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│   SERVIDOR - CONTROLADOR getMyOrders                         │
│                                                              │
│  if (userRole === 'cliente') {                              │
│    // Cliente ve SOLO SUS órdenes                           │
│    orders = await OrderDatabase.findByClienteId(userId)     │
│  }                                                           │
│                                                              │
│  Retorna 200 + orders de ESTE cliente                       │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              CLIENTE - Recibe sus órdenes                    │
│                                                              │
│  [                                                           │
│    { id: "ord_1", cliente_id: "usr_169...", ... },         │
│    { id: "ord_2", cliente_id: "usr_169...", ... }          │
│  ]                                                           │
│                                                              │
│  ✅ Cliente SOLO ve las SUYAS                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. TABLA DE CLAIMS EN JWT

```
CLAIM          TIPO       PROPÓSITO
────────────────────────────────────
id             string     Identificar usuario
email          string     Email del usuario
role           string     Determinar autorización (CRUCIAL)
iat            number     Timestamp de creación (automático)
exp            number     Timestamp de expiración (automático)
```

**CLAIM más importante:** `role`
- Determina qué puede hacer el usuario
- Se valida en cada middleware requireRole()

---

## 3. ÁRBOL DE DECISIÓN: AUTORIZACIÓN

```
Usuario hace request a GET /api/orders/me
con token
│
├─ ¿Header Authorization existe?
│  NO → 401 "No se proporcionó token"
│  SÍ → continúa
│
├─ ¿Token es válido JWT?
│  NO → 401 "Token inválido"
│  SÍ → continúa
│
├─ ¿Token NO ha expirado?
│  SÍ (expiró) → 401 "Token expirado"
│  NO (vigente) → continúa
│
├─ Decodificar token → obtener req.user
│  {
│    id: "usr_169...",
│    email: "cliente@x.cl",
│    role: "cliente"  ← ESTE es el CLAIM
│  }
│
├─ ¿Es usuario cliente?
│  SÍ → Ver SOLO sus órdenes ✅
│  NO → Si es mecanico → Ver sus asignadas
│       Si es admin → Ver TODAS
│
└─ Retornar órdenes filtradas por propiedad
```

---

## 4. PROPIEDAD DE RECURSO (TAREA 5)

```
ESCENARIO 1: Cliente accede a su propia orden

Cliente (id=usr_169) hace:
GET /api/orders/ord_123

Middleware checkOrderOwnership:
├─ Busca orden: { id: "ord_123", clienteId: "usr_169", ... }
├─ ¿orden.clienteId === req.user.id?
│  SÍ → ✅ Acceso permitido → next()
│  NO → ❌ 403 "No tienes permiso"
│
└─ Controlador retorna orden


ESCENARIO 2: Cliente intenta acceder a orden de otro

Cliente (id=usr_111) hace:
GET /api/orders/ord_123  ← Creada por usr_169

Middleware checkOrderOwnership:
├─ Busca orden: { id: "ord_123", clienteId: "usr_169", ... }
├─ ¿orden.clienteId === req.user.id?
│  SÍ (NO) → ❌ 403 "No tienes permiso para acceder a esta orden"
│  (Request se detiene aquí)
│
└─ Controlador NUNCA se ejecuta


ESCENARIO 3: Admin accede a cualquier orden

Admin hace:
GET /api/orders/ord_123

Middleware checkOrderOwnership:
├─ ¿userRole === 'administrador'?
│  SÍ → ✅ Salta verificación → next()
│  NO → Verifica propiedad
│
└─ Controlador retorna orden
```

---

## 5. DIAGRAMA: CÓMO FLUYE UN REQUEST

```
REQUEST ENTRADA:
GET /api/orders/ord_123
Authorization: Bearer eyJhbGc...

        ↓
    
ROUTER: /orders/:orderId

        ↓
    
MIDDLEWARE 1: authMiddleware
├─ Extrae token
├─ Verifica JWT
├─ Decodifica → req.user = { id, email, role }
└─ next()

        ↓
    
MIDDLEWARE 2: checkOrderOwnership
├─ Obtiene orden de BD
├─ Verifica propiedad (según role)
├─ Sí pertenece → req.order = order
└─ next() o 403 STOP

        ↓
    
CONTROLADOR: getOrderById
├─ Usa req.order (ya verificado)
├─ Retorna order
└─ Respuesta 200

        ↓
    
RESPUESTA SALIDA:
{ order: { id, clienteId, estado, ... } }
```

---

## 6. TABLA: MATRIZ DE PERMISOS

```
RECURSO              CLIENTE    MECÁNICO    ADMIN
────────────────────────────────────────────────
GET /orders/me       SUYAS      ASIGNADAS   TODAS
GET /orders/:id      SUYA       ASIGNADA    CUALQUIERA
PATCH /orders/:id    SUYA       ASIGNADA    CUALQUIERA
GET /users           ❌         ❌          ✅
GET /users/:role     ❌         ❌          ✅
```

---

## 7. FLUJO CON VIOLACIÓN DE SEGURIDAD

```
INTENTO: Cliente accede a orden de otro cliente

1. Cliente2 obtiene token con role="cliente", id="usr_222"

2. Intenta: GET /api/orders/ord_123?clienteId=usr_111

3. SERVIDOR recibe:
   - Token válido: ✅
   - role: "cliente" ✅
   - PERO orden pertenece a usr_111

4. checkOrderOwnership middleware:
   ```javascript
   if (order.clienteId !== userId) {
     return res.status(403).json({ 
       error: 'No tienes permiso para acceder a esta orden' 
     });
   }
   ```

5. RESPUESTA: 403 ACCESO DENEGADO

❌ SEGURIDAD VIOLADA PREVENIDA ✅
```

---

## 8. CLAIMS vs AUTENTICACIÓN vs AUTORIZACIÓN

```
AUTENTICACIÓN (¿Eres quien dices ser?)
├─ Email + Password
├─ Bcryptjs compara password
├─ SI VÁLIDO → Generar JWT
└─ Respuesta: token

CLAIMS (¿Qué información llevas?)
├─ Datos codificados en el JWT
├─ id: quién eres
├─ email: tu email
├─ role: qué tipo de usuario
└─ Están en cada request dentro del token

AUTORIZACIÓN (¿Puedes acceder a esto?)
├─ Verifica req.user.role
├─ Verifica propiedad del recurso
├─ SI VÁLIDO → Acceso ✅
├─ SI INVÁLIDO → 403 ❌
└─ Cada middleware verifica algo distinto
```

---

## 9. RESUMEN: CÓMO FUNCIONA TODO JUNTO

```
1. REGISTRO
   Email + Password → Valida → Hashea → Genera JWT con CLAIMS
   
2. LOGIN
   Email + Password → Busca → Compara hash → Genera JWT con CLAIMS
   
3. REQUEST A RUTA PROTEGIDA
   Token en header → Verifica JWT → Extrae CLAIMS
   
4. MIDDLEWARE authMiddleware
   Valida token → Pone req.user = CLAIMS
   
5. MIDDLEWARE requireRole
   Verifica req.user.role esté autorizado
   
6. MIDDLEWARE checkOrderOwnership
   Verifica que req.user.id sea dueño del recurso
   
7. CONTROLADOR
   Accede a recurso que ya fue verificado 3 veces
   
8. RESPUESTA
   Datos del usuario + sus recursos solamente
```

---

## 10. FLUJO DE ERRORES

```
❌ SIN TOKEN
GET /api/orders/me
→ 401 "No se proporcionó token"

❌ TOKEN INVÁLIDO
Authorization: Bearer basura123
→ 401 "Token inválido"

❌ TOKEN EXPIRADO
Authorization: Bearer eyJhbGc... (de hace 25 horas)
→ 401 "Token expirado"

❌ NO AUTORIZADO (rol incorrecto)
GET /api/users (con token cliente)
→ 403 "Acceso denegado para role cliente"

❌ NO ES PROPIETARIO (acceso cruzado)
GET /api/orders/ord_otro (orden de otro cliente)
→ 403 "No tienes permiso para acceder a esta orden"

✅ TODO VÁLIDO
GET /api/orders/mi_orden
→ 200 { order: {...} }
```

---

**Conclusión:** 
El JWT lleva los CLAIMS, los CLAIMS se validan en middleware, y los middleware previenen acceso cruzado entre usuarios.
