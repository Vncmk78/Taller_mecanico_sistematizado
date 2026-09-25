# 🔐 Microservicio de Autenticación - Taller Mecánico

API REST para autenticación con JWT, hashing seguro de contraseñas y autorización por roles.

**Tareas implementadas (Entrega 1/2):**
- ✅ Endpoints de autenticación y consulta del usuario
- ✅ Autorización inicial por roles (cliente, mecánico, administrador)
- ✅ Estudio sobre bcrypt y validación de credenciales
- ✅ Validaciones y manejo seguro de errores de login

---

## 🚀 Empezar

### Instalar dependencias
```bash
cd backend
npm install
```

### Configurar .env
```bash
cp .env.example .env
# Luego editar .env con tus valores
```

### Ejecutar en desarrollo
```bash
npm run dev
```

El servidor estará en: `http://localhost:3001`

---

## 📡 Endpoints

### 🔓 PÚBLICOS

#### POST /api/auth/register
Registra un nuevo usuario
```bash
curl -X POST http://localhost:3001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@taller.cl",
    "password": "Admin@12345",
    "name": "Administrador",
    "role": "administrador"
  }'
```

**Respuesta (201):**
```json
{
  "message": "Usuario creado exitosamente",
  "user": {
    "id": "usr_1694800000...",
    "email": "admin@taller.cl",
    "name": "Administrador",
    "role": "administrador",
    "isActive": true,
    "createdAt": "2024-01-15..."
  },
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Validaciones:**
- Email: formato válido y único
- Contraseña: mín 8 caracteres, 1 mayúscula, 1 número
- Role: `cliente`, `mecanico` o `administrador`

#### POST /api/auth/login
Autentica un usuario
```bash
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@taller.cl",
    "password": "Admin@12345"
  }'
```

**Respuesta (200):**
```json
{
  "message": "Login exitoso",
  "user": { ... },
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Error (401):**
```json
{
  "error": "Credenciales inválidas"
}
```
*Nota: Mismo error si email no existe o contraseña es incorrecta (seguridad)*

### 🔒 PROTEGIDOS (requieren Authorization: Bearer <token>)

#### GET /api/auth/profile
Obtiene perfil del usuario autenticado
```bash
curl -X GET http://localhost:3001/api/auth/profile \
  -H "Authorization: Bearer tu_token_aqui"
```

**Respuesta (200):**
```json
{
  "message": "Perfil obtenido",
  "user": {
    "id": "usr_1694800000...",
    "email": "admin@taller.cl",
    "name": "Administrador",
    "role": "administrador",
    "isActive": true
  }
}
```

#### GET /api/auth/verify
Verifica que el token es válido
```bash
curl -X GET http://localhost:3001/api/auth/verify \
  -H "Authorization: Bearer tu_token_aqui"
```

**Respuesta (200):**
```json
{
  "message": "Token válido",
  "user": {
    "id": "usr_1694800000...",
    "email": "admin@taller.cl",
    "role": "administrador"
  }
}
```

#### POST /api/auth/logout
Cierra la sesión (cliente elimina el token)
```bash
curl -X POST http://localhost:3001/api/auth/logout \
  -H "Authorization: Bearer tu_token_aqui"
```

### 👮 SOLO ADMINISTRADOR

#### GET /api/auth/users
Obtiene todos los usuarios (solo admin)
```bash
curl -X GET http://localhost:3001/api/auth/users \
  -H "Authorization: Bearer token_admin"
```

**Respuesta (200):**
```json
{
  "message": "Usuarios obtenidos",
  "count": 2,
  "users": [ { ... } ]
}
```

#### GET /api/auth/users/:role
Obtiene usuarios por rol (solo admin)
```bash
curl -X GET http://localhost:3001/api/auth/users/cliente \
  -H "Authorization: Bearer token_admin"
```

---

## 🛡️ Seguridad Implementada

### Hashing de Contraseñas (bcryptjs)
- ✅ Contraseñas hasheadas con bcrypt (10 rounds)
- ✅ Comparación segura al login
- ✅ Nunca se retorna passwordHash

### Validación de Credenciales
- ✅ Email: validación de formato
- ✅ Contraseña: 8+ caracteres, mayúscula, número
- ✅ Mismo error para email inexistente o contraseña incorrecta

### JWT (JSON Web Tokens)
- ✅ Tokens con expiración (24 horas)
- ✅ Algoritmo HS256
- ✅ Claims: id, email, role

### Autorización por Roles
- ✅ Middleware `requireRole()` para rutas protegidas
- ✅ Admin puede listar usuarios
- ✅ Usuarios regulares no pueden acceder a /users

### Manejo de Errores Seguro
- ✅ No revelar información sensible
- ✅ Mensajes genéricos de error
- ✅ HTTP status codes apropiados

---

## 📚 Documentación

Ver: `ESTUDIO_BCRYPT_Y_VALIDACION.md`
- ¿Por qué no guardar contraseñas en texto plano?
- ¿Cómo funciona bcrypt?
- Validaciones seguras
- Diferencia entre hashing vs encriptación

---

## 🏗️ Estructura

```
backend/
├── src/
│   ├── index.js                 # Servidor principal
│   ├── config/
│   │   └── jwt.config.js        # Configuración de JWT
│   ├── models/
│   │   └── User.js              # Modelo User con bcrypt
│   ├── database/
│   │   ├── users.db.js          # Base de datos simulada
│   │   └── users.json           # Datos en JSON
│   ├── utils/
│   │   └── jwt.util.js          # Utilidades JWT
│   ├── middleware/
│   │   └── auth.middleware.js   # Auth y autorización
│   ├── controllers/
│   │   └── auth.controller.js   # Lógica de autenticación
│   └── routes/
│       └── auth.routes.js       # Rutas de auth
├── .env                         # Variables de entorno
├── .env.example                 # Ejemplo .env
├── .gitignore                   # Archivos ignorados
├── package.json
└── README.md
```

---

## 🧪 Testing

### Crear usuario admin
```bash
# POST /api/auth/register
{
  "email": "admin@taller.cl",
  "password": "Admin@12345",
  "name": "Admin Sistema",
  "role": "administrador"
}
```

### Crear usuario cliente
```bash
{
  "email": "cliente@taller.cl",
  "password": "Cliente@123",
  "name": "Cliente Test",
  "role": "cliente"
}
```

### Probar login
```bash
# POST /api/auth/login
{
  "email": "admin@taller.cl",
  "password": "Admin@12345"
}
```

### Probar acceso con token
```bash
# GET /api/auth/profile
# Header: Authorization: Bearer <token_del_login>
```

### Probar autorización
```bash
# GET /api/auth/users (con token de admin)
# ✅ Debería funcionar

# GET /api/auth/users (con token de cliente)
# ❌ Debería retornar 403 Acceso denegado
```

---

## ⚠️ Errores Comunes

**Error:** "Port 3001 already in use"
```bash
# Cambiar en .env:
PORT=3002
```

**Error:** "JWT_SECRET is undefined"
```bash
# Asegúrate de que .env exista y tenga JWT_SECRET
```

**Error:** "Cannot find module"
```bash
npm install
```

---

## 📝 Notas de Desarrollo

- BD simulada con JSON para desarrollo
- En producción: usar MongoDB, PostgreSQL, etc
- Cambiar JWT_SECRET en .env para producción
- Implementar rate limiting para login
- Agregar logs de intentos fallidos

---

**Próxima entrega:** 
- Comprobaciones de propiedad de recurso
- Documentación completa de flujo
- Pruebas de acceso cruzado entre roles

