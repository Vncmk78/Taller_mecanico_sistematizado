# 📚 ESTUDIO: Hashing Seguro de Contraseñas y Validación de Credenciales

**Asignatura:** Taller de Integración II  
**Año:** 4to Ingeniería Civil Informática  
**Fecha:** Septiembre 2024

---

## 1. ¿POR QUÉ NO ALMACENAR CONTRASEÑAS EN TEXTO PLANO?

Si guardamos contraseñas así:
```
usuario@example.com -> Contraseña123
admin@taller.cl -> Admin1234
```

**Problemas:**
- ❌ Si la BD se filtra, todos ven todas las contraseñas
- ❌ Si un desarrollador ve la BD, conoce las contraseñas
- ❌ No cumple con regulaciones (GDPR, HIPAA, etc)
- ❌ Es un desastre de seguridad

---

## 2. ¿QUÉ ES BCRYPTJS?

**Bcryptjs** es una librería de JavaScript que implementa el algoritmo **bcrypt** para hash seguro de contraseñas.

### Características:
- **One-way:** No se puede desencriptar (a diferencia de `Base64`)
- **Adaptive:** Se ralentiza con el tiempo (resistencia a fuerza bruta)
- **Salted:** Cada hash es único incluso con misma contraseña
- **Cross-platform:** Funciona en Node.js, navegadores, etc

### Diferencia: SHA-256 vs Bcrypt

**SHA-256 (MALO para contraseñas):**
```javascript
const hash = sha256("MiContraseña123");
// Resultado: aa3e827f6c...
// Problema: Es muy rápido (millones de hashes/seg)
// Un atacante puede probar 1 millón de contraseñas por segundo
```

**Bcrypt (BUENO para contraseñas):**
```javascript
const hash = bcrypt("MiContraseña123", 10 rounds);
// Resultado: $2b$10$SlOZD4G0pKX0yQ8...
// Ventaja: Tarda ~100ms por hash
// Un atacante puede probar solo ~10 contraseñas por segundo
```

---

## 3. CÓMO FUNCIONA BCRYPT EN NUESTRO CÓDIGO

### Paso 1: Registro (Hashear contraseña nueva)

```javascript
// Usuario registra: "Admin@12345"
const password = "Admin@12345";

// 1. Bcrypt genera un SALT aleatorio
// 2. Combina salt + contraseña
// 3. Aplica el algoritmo bcrypt 10 veces (rounds)
const passwordHash = await bcrypt.hash(password, 10);
// Resultado: $2b$10$N9qo8uLOickgx2ZMRZoMy.eIJqR9iFcvHBU...

// 4. Guardamos el hash en la BD (NO la contraseña)
db.users.create({
  email: "admin@taller.cl",
  passwordHash: "$2b$10$N9qo8uLOickgx2ZMRZoMy.eIJqR9iFcvHBU...",
  name: "Admin"
});
```

### Paso 2: Login (Comparar contraseña)

```javascript
// Usuario intenta login con: "Admin@12345"
const plainPassword = "Admin@12345";

// 1. Obtener hash guardado en BD
const user = db.users.find({ email: "admin@taller.cl" });
// user.passwordHash = "$2b$10$N9qo8uLOickgx2ZMRZoMy.eIJqR9iFcvHBU..."

// 2. Bcrypt compara el plaintext con el hash
const isValid = await bcrypt.compare(plainPassword, user.passwordHash);
// Resultado: true (si es la contraseña correcta)

if (isValid) {
  // ✅ Login exitoso, generar JWT
  const token = jwt.sign({ id: user.id }, SECRET);
} else {
  // ❌ Contraseña incorrecta
  return res.status(401).json({ error: "Credenciales inválidas" });
}
```

### Paso 3: Contraseña incorrecta

```javascript
// Usuario intenta login con: "MiContraseña123" (INCORRECTA)
const plainPassword = "MiContraseña123";

const isValid = await bcrypt.compare(
  plainPassword, 
  "$2b$10$N9qo8uLOickgx2ZMRZoMy.eIJqR9iFcvHBU..."
);
// Resultado: false

// ❌ Rechazar login
```

---

## 4. PARÁMETRO "ROUNDS" - ¿QUÉ ES?

**Rounds = número de veces que se aplica el algoritmo**

```javascript
bcrypt.hash(password, 10);
//                     ^^-- rounds
```

| Rounds | Tiempo aprox | Seguridad | Recomendación |
|--------|-------------|----------|---------------|
| 5      | ~10ms       | Baja     | ❌ No usar |
| 8      | ~40ms       | Media    | ⚠️ Aceptable |
| 10     | ~100ms      | Buena    | ✅ Recomendado |
| 12     | ~250ms      | Muy buena | ✅ Excelente |
| 15     | ~1s         | Excelente | ✅ Para datos muy sensibles |

**En nuestro código:**
```
BCRYPT_ROUNDS=10  // Nosotros usamos 10 (buen balance)
```

**¿Por qué más rounds = más seguro?**
- Si usamos 5 rounds: Un atacante puede probar ~100 contraseñas/segundo
- Si usamos 10 rounds: Puede probar ~10 contraseñas/segundo
- Si usamos 15 rounds: Puede probar ~1 contraseña/segundo

---

## 5. VALIDACIÓN DE CREDENCIALES - BUENAS PRÁCTICAS

### ❌ LO QUE NO HACER

```javascript
// MAL: Revelar información sensible
if (!user) {
  return res.status(401).json({ 
    error: "El email no está registrado" // ❌ Indica que el email no existe
  });
}

if (!isPasswordValid) {
  return res.status(401).json({ 
    error: "Contraseña incorrecta" // ❌ Indica que el email SÍ existe
  });
}
```

**¿Por qué es malo?**
Un atacante puede:
1. Probar emails comunes
2. Si recibe "credenciales inválidas" → email no existe
3. Si recibe "contraseña incorrecta" → email SÍ existe
4. Ahora conoce qué emails están en el sistema

### ✅ LO QUE HACER (Nuestro código)

```javascript
// BIEN: Mismo mensaje para ambos casos
if (!user || !isPasswordValid) {
  return res.status(401).json({ 
    error: "Credenciales inválidas" // ✅ No revela qué es incorrecto
  });
}
```

**Ventajas:**
- Atacante no puede enumerar usuarios válidos
- Un mensaje genérico para cualquier error
- Más seguro ✅

### Otros ejemplos de validación segura

```javascript
// Email válido
const validateEmail = (email) => {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email);
};

// Contraseña con requisitos
const validatePassword = (password) => {
  if (password.length < 8) return false;
  if (!/[A-Z]/.test(password)) return false; // Al menos una mayúscula
  if (!/[0-9]/.test(password)) return false; // Al menos un número
  return true;
};

// Entonces al registrar:
if (!validateEmail(email)) {
  return res.status(400).json({ error: "Email inválido" });
}

const validation = validatePassword(password);
if (!validation.valid) {
  return res.status(400).json({ error: validation.message });
}
```

---

## 6. FLOW COMPLETO: REGISTRO Y LOGIN

```
REGISTRO:
1. Usuario entra email: admin@taller.cl, contraseña: Admin@12345
2. Servidor valida: ✓ email formato, ✓ contraseña requisitos
3. Servidor verifica: ✓ email no existe
4. Servidor HASHEA: bcrypt.hash("Admin@12345", 10) → $2b$10$N9q...
5. Servidor GUARDA en BD: { email, passwordHash, name, role }
6. Servidor GENERA JWT con claims: { id, email, role }
7. Servidor RETORNA: { user, token }
8. Frontend GUARDA token en localStorage

LOGIN:
1. Usuario entra email: admin@taller.cl, contraseña: Admin@12345
2. Servidor busca usuario en BD por email
3. Si NO existe: retornar "Credenciales inválidas"
4. Si SÍ existe: bcrypt.compare("Admin@12345", passwordHash)
5. Si NO coincide: retornar "Credenciales inválidas"
6. Si SÍ coincide: GENERAR JWT y RETORNAR token
7. Frontend GUARDA token
8. Próximas requests: Authorization: Bearer <token>

RUTAS PROTEGIDAS:
1. Frontend hace GET /api/auth/profile con header Authorization
2. Servidor EXTRAE token del header
3. Servidor VERIFICA token con JWT
4. Si inválido: retornar 401 "Token inválido"
5. Si válido: DECODIFICAR y obtener req.user
6. RETORNAR datos del usuario
```

---

## 7. CÓDIGO EN NUESTRO PROYECTO

### Registro (User.js)
```javascript
static async hashPassword(password, rounds) {
  return await bcrypt.hash(password, rounds);
}
```

### Login (auth.controller.js)
```javascript
const isPasswordValid = await user.comparePassword(password);
if (!isPasswordValid) {
  return res.status(401).json({ error: 'Credenciales inválidas' });
}
```

### Comparación (User.js)
```javascript
async comparePassword(plainPassword) {
  return await bcrypt.compare(plainPassword, this.passwordHash);
}
```

---

## 8. RESUMEN DE SEGURIDAD

| Concepto | Seguridad | Explicación |
|----------|-----------|-------------|
| **Texto plano** | ❌ Crítica | Visible si la BD se filtra |
| **SHA-256** | ⚠️ Débil | Demasiado rápido para probar contraseñas |
| **bcrypt** | ✅ Excelente | Lento y adaptativo |
| **Mismo error** | ✅ Bueno | No revela si email existe |
| **Emails únicos** | ✅ Bueno | Previene duplicados |
| **Validación fuerte** | ✅ Bueno | Requisitos mínimos de contraseña |

---

## 9. ¿CÓMO MEJORARLO?

Para un sistema más seguro:
- ✅ Implementar rate limiting (máx 5 intentos/minuto)
- ✅ Agregar 2FA (Two-Factor Authentication)
- ✅ Tokens de recuperación de contraseña
- ✅ Logs de intentos fallidos
- ✅ HTTPS obligatorio en producción
- ✅ Expiración de tokens (nuestro proyecto: 24h)

---

## 10. REFERENCIAS

- Bcryptjs docs: https://github.com/dcodeIO/bcrypt.js
- OWASP Password Guidelines: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- JSON Web Tokens: https://jwt.io/

---

**Conclusión:** Bcrypt es la forma estándar industrial de proteger contraseñas. Úsalo siempre para cualquier sistema que guarde contraseñas. 🔐
