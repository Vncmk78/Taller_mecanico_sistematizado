# Estudio: Recomendaciones OWASP relacionadas con autenticación y control de acceso

**Proyecto:** Taller mecánico sistematizado (INFO1156 - Clean Architecture)
**Fecha:** 2026-10-29
**Alcance:** MS1 (Autenticación y Usuarios), JWT compartido (shared/auth), guardas de autorización, Gateway y comportamiento transversal.

## 1. Referencias OWASP
- OWASP Authentication Cheat Sheet
- OWASP Authorization Cheat Sheet
- OWASP Session Management Cheat Sheet (aplicación parcial por uso JWT stateless)

## 2. Mapeo con la implementación actual

| Recomendación OWASP | Estado | Evidencia en el proyecto | Comentario |
|---|---|---|---|
| **Almacenamiento seguro de contraseñas** (bcrypt/Argon2, evitar MD5/SHA1) | Cumple | ackend/services/ms1_auth/security/passwords.py - crypt con hashpw/gensalt, validación max 72 bytes | Correcto. Solo MS1 gestiona credenciales. |
| **Errores genéricos en autenticación** (evitar enumeración de usuarios) | Cumple (endurecido) | services/ms1_auth/services/autenticacion.py - CredencialesInvalidasError("Correo o contraseña incorrectos"), error_no_autenticado | Tras el endurecimiento se añade **hash dummy** para usuarios inexistentes y mismo tratamiento para cuentas inactivas. |
| **Protección contra fuerza bruta / credential stuffing** | Parcial | utenticacion.py: intentos_fallidos, loqueado_hasta, CuentaBloqueadaError -> 429 con Retry-After; config LOGIN_MAX_INTENTOS, LOGIN_BLOQUEO_MINUTOS | Bloqueo **por cuenta** implementado. Falta *rate limiting* transversal por IP/dispositivo. |
| **Normalización de respuestas 401/403** | Cumple | shared/errores_auth.py - error_no_autenticado() con WWW-Authenticate: Bearer, error_sin_permiso() | Unificado en todos los microservicios. |
| **Uso centralizado de JWT** (una fuente de verdad) | Cumple | shared/auth.py - emisión/validación, claims sub, oles, algoritmo HS256. Usado por gateway/servicios. | Respeta la regla del proyecto. |
| **Autorización por roles / least privilege** | Cumple | services/ms1_auth/dependencies.py equerir_roles() valida que al menos un rol coincida; aplicado en MS1/MS2/MS3. MS3 valida argumentos no vacíos. | Bien aplicado. |
| **Validación de entrada** (schemas) | Cumple | services/ms1_auth/schemas/auth.py - Pydantic con EmailStr, min_length, extra="forbid". | Sólido para registro/login. |
| **Manejo de cuentas sin roles** | Cumple | uth.py (login): UsuarioSinRolesError -> 403. /auth/me tolera oles: []. oles_del_usuario() lanza si vacío. | Alineado con la corrección ya realizada. |
| **Protección de endpoints sensibles** | Cumple | Endpoints administrativos usan equerir_roles(ADMINISTRADOR). Guardas por servicio. | Correcto. |
| **Revocación / logout** | Pendiente | Stateless JWT sin jti ni blacklist. | No existe mecanismo de revocación. Cambiaría arquitectura (requiere store compartido). |
| **Refresh tokens / rotación** | Pendiente | Solo access token (JWT_EXPIRE_MINUTES). | No implementado. |
| **Política de contraseñas** (complejidad/longitud mínima) | Parcial | min_length=8 en registro. Sin mayúsculas/números/símbolos obligatorios ni chequeo contra listas. | Mínimo aceptable, mejorable. |
| **Enumeración por registro** | Parcial (diseño actual) | POST /auth/register devuelve 409 si el correo ya existe. | Válido y documentado; trade-off aceptado frente a ocultarlo. |
| **Transmisión segura** | Fuera de código app | Requiere HTTPS en despliegue. | Responsabilidad de infraestructura. |

## 3. Hallazgos tras el endurecimiento

Con los cambios aplicados a services/ms1_auth/services/autenticacion.py:
- **Anti-enumeración por tiempo:** erificar_contrasena(contrasena, _DUMMY_HASH_VERIFICACION) cuando el correo no existe.
- **Unificación con cuentas inactivas:** mismo camino genérico, sin filtrar estado.
- **Rollback limpio:** si usuario is None en _registrar_intento_fallido.
- **Bloqueo conservado:** 429 con Retry-After y reinicio en login correcto.

## 4. Recomendaciones prácticas

| Prioridad | Recomendación | Notas |
|---|---|---|
| **Alta** | Añadir *rate limiting* en Gateway para /auth/login, /auth/register (por IP + ventana temporal) | Complementa el bloqueo por cuenta (protege contra ataques distribuidos). |
| **Media** | Evaluar lista negra de tokens (jti) para logout o revocación forzosa | Requiere Redis/tabla compartida. Actualmente stateless es coherente con el proyecto. |
| **Media** | Reforzar política de contraseñas (complejidad) | Ajustar schema + mensaje claro; tener en cuenta compatibilidad con usuarios existentes. |
| **Baja** | Considerar *account lockout notification* (email) | Requiere servicio de notificaciones, fuera del alcance actual. |

## 5. Conclusión
La implementación es **sólida** para un proyecto académico con arquitectura limpia. Lo esencial de OWASP (contraseñas seguras, errores genéricos, bloqueo por fuerza bruta, autorización por roles, JWT centralizado) está cubierto. El endurecimiento reciente (hash dummy + unificación de errores) mejora la resistencia a enumeración sin romper el contrato existente.
