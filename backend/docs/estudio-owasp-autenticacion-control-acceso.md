# Estudio: recomendaciones OWASP de autenticación y control de acceso

**Proyecto:** Taller mecánico sistematizado (INFO1156 — Clean Architecture)
**Fecha:** 2026-11-03 (reemplaza la versión del 2026-10-29)
**Rama estudiada:** `DerisA`
**Ámbito:** MS1 (`backend/services/ms1_auth`), contrato JWT (`backend/shared/auth.py`),
respuestas 401/403 (`backend/shared/errores_auth.py`), guardas de MS2/MS3/MS4 y
configuración de la Gateway.

**Estado:** estudio sobre el código en ejecución. **No introduce cambios de
comportamiento.** Los hallazgos de la sección 6 quedan documentados y las
recomendaciones de la sección 7 quedan pendientes de decisión del equipo.

> **Nota sobre la versión anterior.** La versión del 2026-10-29 tenía texto dañado
> (rutas y nombres sin su primera letra, por ejemplo `ackend/`, `crypt`,
> `equerir_roles`, y caracteres de control dentro del archivo) y afirmaba que las
> cuentas inactivas reciben el mismo tratamiento que las inexistentes. Esa
> afirmación es cierta para el **mensaje**, pero no para el **tiempo** de
> respuesta (ver H6). Esta versión corrige ambas cosas y agrega los hallazgos
> verificados de la sección 6.

---

## 1. Fuentes OWASP consultadas

| Fuente | Qué aporta a este estudio |
|---|---|
| **OWASP Top 10:2025 — A07 Authentication Failures** | Riesgos de autenticación: fuerza bruta, *credential stuffing*, contraseñas débiles, sesiones que no se invalidan. |
| **OWASP Top 10:2025 — A01 Broken Access Control** | Riesgos de autorización: denegar por defecto, verificar en el servidor en cada petición, IDOR, escalada de privilegios. |
| **ASVS 5.0** — V6 Authentication, V7 Session Management, V8 Authorization, V9 Self-contained Tokens | Requisitos verificables; se usan como lista de control. |
| **Cheat Sheets**: Authentication, Password Storage, Credential Stuffing Prevention, Authorization, IDOR Prevention, JSON Web Token, Session Management | Recomendaciones concretas de implementación. |

Las URL están en la sección 9.

## 2. Método

1. Lectura del código de autenticación y autorización de la rama `DerisA`.
2. Contraste de cada recomendación OWASP con su evidencia en el código.
3. Ejecución de la suite de pruebas de autenticación y autorización (sección 8).
4. Verificación empírica de los hallazgos nuevos con un script de prueba
   temporal, **fuera del repositorio** (sección 8).

Estados usados: ✅ Cumple · ⚠️ Parcial · ❌ No cumple · ℹ️ Fuera del código de la aplicación.

Este estudio complementa, sin repetirlos en detalle, a
`estudio-fallos-jwt-ataques-credenciales.md` (códigos `J*` y `C*`),
`estudio-rbac-multiples-roles.md` y `matriz-autorizacion-roles.md`.

---

## 3. Autenticación (A07:2025 · ASVS V6)

| # | Recomendación OWASP | Estado | Evidencia en el proyecto |
|---|---|---|---|
| A1 | Guardar contraseñas con un algoritmo lento y con sal (bcrypt, Argon2id, scrypt) | ✅ | `ms1_auth/security/passwords.py`: `bcrypt.hashpw` con `bcrypt.gensalt()` (coste 12 por defecto). Nunca se guarda texto plano. |
| A2 | No truncar contraseñas en silencio (bcrypt ignora más de 72 bytes) | ✅ | `hash_contrasena` rechaza contraseñas de más de 72 bytes; `verificar_contrasena` devuelve `False` ante error. |
| A3 | Longitud mínima de 8 y sin reglas de composición forzadas; revisar contra contraseñas filtradas | ⚠️ | `schemas/auth.py`: `min_length=8`. No hay revisión contra listas de contraseñas comunes o filtradas. OWASP **no** pide mayúsculas/símbolos obligatorios, así que no hace falta agregarlos. |
| A4 | Mensaje genérico ante credenciales incorrectas (no revelar si el correo existe) | ✅ | `autenticacion.py`: «Correo o contraseña incorrectos» para correo inexistente, contraseña mala y cuenta inactiva; `error_no_autenticado` agrega `WWW-Authenticate: Bearer`. |
| A5 | Mismo tiempo de respuesta en todos los casos de error | ⚠️ | Correo inexistente: se verifica contra `_DUMMY_HASH_VERIFICACION` (mitiga C4). Cuenta **inactiva**: el `and` corta antes de bcrypt y responde más rápido (ver H6). |
| A6 | Que la protección contra fuerza bruta no sirva para enumerar cuentas | ❌ | El bloqueo responde `429` solo cuando la cuenta existe; un correo inexistente responde siempre `401` (ver H1). |
| A7 | Protección contra fuerza bruta por cuenta | ✅ | `LOGIN_MAX_INTENTOS=5`, `LOGIN_BLOQUEO_MINUTOS=15`, `429` + `Retry-After`; `test_login_intentos_fallidos.py`. |
| A8 | Protección contra *credential stuffing* y *password spraying* (límite por IP o dispositivo) | ❌ | No hay *rate limiting* en la Gateway ni en MS1. El bloqueo por cuenta no frena un ataque que prueba una contraseña contra muchas cuentas. |
| A9 | Evitar que el bloqueo permita negar el servicio a un usuario legítimo | ⚠️ | Cualquiera que conozca un correo puede bloquearlo 15 minutos con 5 intentos (ver H2). |
| A10 | El registro no debe permitir elegir privilegios | ✅ | `extra="forbid"` y el rol `cliente` lo asigna el servidor. |
| A11 | No revelar existencia de cuentas en el registro | ⚠️ | `POST /auth/register` responde `409` «El correo ya está registrado» (C5). *Trade-off* aceptado por experiencia de usuario. |
| A12 | Registrar eventos de autenticación (éxitos, fallos, bloqueos) | ❌ | MS1 no registra eventos de login. Decisión previa del equipo (C11): solo contador y bloqueo. |
| A13 | MFA para cuentas privilegiadas | ❌ | No implementado (C12). |
| A14 | Transmitir credenciales solo por TLS | ℹ️ | Depende del despliegue (Vercel sirve HTTPS). Ver `estudio-seguridad-transporte.md`. |

## 4. Tokens autocontenidos — JWT (ASVS V9 · JWT Cheat Sheet · Session Management)

| # | Recomendación OWASP | Estado | Evidencia en el proyecto |
|---|---|---|---|
| T1 | Una sola implementación de emisión y validación | ✅ | `shared/auth.py` es la única fuente de verdad; MS1–MS4 llaman a `validar_token_acceso`. |
| T2 | Fijar el algoritmo y rechazar `none` | ✅ | `algorithms=[algoritmo]` y `_validar_configuracion` solo admite `HS256`. |
| T3 | Clave secreta fuerte y fuera del código | ✅ | `JWT_SECRET_KEY: SecretStr = Field(min_length=32)`, leída del entorno; `_validar_configuracion` exige 32 caracteres. |
| T4 | Exigir y validar `exp` y `sub` | ✅ | `options={"require_exp": True, "require_sub": True}`; `sub` debe ser entero positivo. |
| T5 | Validar el contenido de los claims | ✅ | `roles` debe ser lista no vacía, sin duplicados y con roles conocidos. |
| T6 | Vida corta del token | ✅ | `JWT_EXPIRE_MINUTES=60`. |
| T7 | Poder invalidar tokens (logout, cambio de privilegios, desactivación) | ❌ | No hay `jti`, lista de revocación ni versión de token (J10, J11). Ver H4. |
| T8 | No guardar en el token datos sensibles | ✅ | Solo `sub`, `roles`, `exp`. |
| T9 | Compartir el secreto entre el mínimo de servicios | ⚠️ | El mismo secreto HS256 vive en MS1–MS4 (J12): quien lea el entorno de cualquiera puede forjar tokens válidos para todos. La Gateway no lo tiene. |

## 5. Control de acceso (A01:2025 · ASVS V8 · Authorization Cheat Sheet)

| # | Recomendación OWASP | Estado | Evidencia en el proyecto |
|---|---|---|---|
| AC1 | Verificar en el servidor, en cada petición | ✅ | Cada microservicio valida el JWT en sus dependencias (`obtener_principal_actual`); la Gateway no decide permisos. |
| AC2 | Denegar por defecto | ✅ | Sin token o con token inválido: `401`; `requerir_roles` exige al menos un rol permitido. |
| AC3 | Mínimo privilegio por rol | ✅ | Endpoints administrativos con `requerir_roles(NombreRol.ADMINISTRADOR)`; matriz en `matriz-autorizacion-roles.md`. |
| AC4 | Respuestas de error uniformes | ✅ | `shared/errores_auth.py`: un solo mensaje para `401` y otro para `403`; `test_normalizacion_401_403.py`. |
| AC5 | Evitar IDOR: comprobar que el recurso pertenece a quien lo pide | ✅ / ⚠️ | Cubierto para cliente en órdenes, vehículos y evidencias (`test_acceso_recursos_ajenos_mismo_rol.py`). Quedan dos huecos declarados como `xfail` estricto en `test_acceso_indebido_roles.py`: mecánico no asignado en MS3 (matriz §4.4) y `mecanico_id` sin validar en MS2 (matriz §4.3). |
| AC6 | Los cambios de permisos deben surtir efecto de inmediato | ❌ | Los guardas deciden con los roles del token; un rol retirado o una cuenta desactivada siguen autorizados hasta que expira (H4). Solo `/auth/me` relee la base. |
| AC7 | Proteger contra escalada y pérdida de administración | ⚠️ | Un administrador puede retirarse su propio rol y dejar el sistema sin administradores (H3). |
| AC8 | Registrar fallos de autorización | ❌ | No se registran los `403`. |
| AC9 | CORS restringido a orígenes de confianza | ⚠️ | La Gateway acepta cualquier `https://*.vercel.app` con `allow_credentials=True` (H5). |

---

## 6. Hallazgos verificados

### H1 — El bloqueo revela qué cuentas existen (A6) · Severidad media

El mensaje del login es uniforme, pero el **código de estado** no. Tras 5 intentos
fallidos, un correo registrado empieza a responder `429` con `Retry-After`; un
correo que no existe responde `401` para siempre, porque
`_registrar_intento_fallido` no tiene cuenta a la que contar el fallo.

Verificado:

```
correo existente:   [401, 401, 401, 401, 401, 429]
correo inexistente: [401, 401, 401, 401, 401, 401]
```

Esto anula la protección de A4 con solo seis peticiones por correo. OWASP
(Authentication Cheat Sheet, *Account Lockout*) pide que la respuesta del bloqueo
no permita distinguir cuentas.

### H2 — El bloqueo puede usarse para negar el servicio (A9) · Severidad media

Como el bloqueo es por cuenta y no exige nada más, cualquiera que conozca el
correo de un administrador o de un mecánico puede dejarlo sin acceso 15 minutos,
y repetirlo indefinidamente. OWASP recomienda combinar el bloqueo por cuenta con
límites por IP, retardos progresivos o un desafío (CAPTCHA) en lugar de un
bloqueo duro.

### H3 — Un administrador puede quitarse su propio rol · Severidad media

`DELETE /auth/usuarios/{usuario_id}/roles/administrador` no impide que el
`usuario_id` sea el del propio administrador ni comprueba si es el último.
Verificado: el autorretiro responde `200` y la cuenta queda con `roles: []`; desde
ese momento ya no puede iniciar sesión (`403` «El usuario no posee roles»). Si
era el único administrador, nadie puede volver a asignar roles sin tocar la base
de datos.

### H4 — Rol retirado o cuenta desactivada siguen autorizados hasta que expira el token (AC6, T7) · Severidad media

Amplía J11. Verificado con un mismo token de administrador:

| Paso | Resultado |
|---|---|
| El administrador se retira su rol | `200` |
| `GET /auth/usuarios` (exige administrador) con el token anterior | `200` — sigue entrando |
| Se desactiva la cuenta (`activo = false`) | — |
| `GET /auth/me` | `401` — relee la base |
| `GET /auth/usuarios` | `200` — sigue entrando |

La ventana es de hasta `JWT_EXPIRE_MINUTES` (60 min) y afecta a los cuatro
microservicios, porque ninguno consulta MS1 para autorizar.

### H5 — CORS acepta cualquier subdominio de Vercel con credenciales (AC9) · Severidad baja

`gateway/config.py` define `CORS_ORIGIN_REGEX = r"https://[a-z0-9-]+\.vercel\.app"`
y `CORS_ALLOW_CREDENTIALS = True`. Cualquier proyecto alojado en Vercel, no solo
los del equipo, queda como origen de confianza. El impacto real es bajo porque el
token viaja en la cabecera `Authorization` y no en cookies, pero OWASP recomienda
una lista explícita de orígenes.

### H6 — Las cuentas inactivas responden más rápido (A5) · Severidad baja

El correo inexistente ya pasa por bcrypt con el hash *dummy*, así que C4 quedó
**parcialmente** mitigado. Pero en
`usuario is not None and usuario.activo and verificar_contrasena(...)`, una cuenta
inactiva corta en `usuario.activo` y no ejecuta bcrypt; la rama `elif not usuario.activo`
solo tiene `pass`. Por tiempo de respuesta se puede saber que una cuenta existe y
está desactivada.

---

## 7. Recomendaciones (pendientes de decisión del equipo)

| Prioridad | Recomendación | Resuelve | Notas |
|---|---|---|---|
| Alta | *Rate limiting* por IP en la Gateway para `/api/auth/login` y `/api/auth/register` | A8, H2 | Complementa el bloqueo por cuenta. En serverless requiere un almacén compartido (por ejemplo Redis) o el *firewall* de la plataforma. |
| Alta | Responder igual (`401`) mientras dura el bloqueo, o aplicar el mismo contador a correos inexistentes | H1 | Mantener `Retry-After` solo si se aplica también a correos inexistentes. |
| Alta | Impedir que un administrador se retire su propio rol de administrador, o que se retire el último | H3 | Regla de negocio en `services/autenticacion.py` (capa de servicio, no en el router). |
| Media | Revalidar la cuenta en operaciones sensibles o agregar una versión de token (`token_version` en `usuario`, claim en el JWT) | H4, T7, AC6 | Hasta entonces, documentar la ventana de 60 min y considerar bajar `JWT_EXPIRE_MINUTES`. |
| Media | Ejecutar `verificar_contrasena` con el hash *dummy* también para cuentas inactivas | H6 | Cambio de una línea en `autenticar_usuario`. |
| Media | Cerrar los dos huecos de la matriz (mecánico no asignado en MS3; `mecanico_id` en MS2) | AC5 | Ya tienen pruebas `xfail(strict=True)` que pasarán a fallar cuando se corrijan. |
| Baja | Lista explícita de orígenes CORS en lugar de la regex de Vercel | H5, AC9 | Configurable por `GATEWAY_CORS_ORIGIN_REGEX`. |
| Baja | Revisar contraseñas nuevas contra una lista de contraseñas comunes | A3 | Sin reglas de composición, según OWASP. |
| Baja | Registrar logins fallidos, bloqueos y `403` (sin datos sensibles) | A12, AC8 | Revisar la decisión C11 del equipo. |

---

## 8. Cómo se verificó

**Pruebas del proyecto** (Python 3.13, desde `backend/`):

```bash
python -m pytest -q tests/test_auth_api.py tests/test_seguridad_autenticacion.py \
  tests/test_login_intentos_fallidos.py tests/test_jwt.py tests/test_integridad_token_jwt.py \
  tests/test_autorizacion.py tests/test_acceso_indebido_roles.py \
  tests/test_acceso_recursos_ajenos_mismo_rol.py tests/test_normalizacion_401_403.py \
  tests/test_usuarios_roles.py tests/test_historial_roles.py tests/test_autenticacion_canales.py
```

Resultado: **138 passed, 4 xfailed**. Los 4 `xfail` son los huecos ya declarados
de la matriz (AC5).

**Verificación de H1, H3 y H4:** script de pytest temporal, ejecutado con los
fixtures `db` y `api` de `tests/conftest.py` y guardado fuera del repositorio
(no se agregó al proyecto). Resultados copiados en la sección 6.

**H2, H5 y H6** se verificaron por lectura de código (`autenticacion.py`,
`gateway/config.py`).

## 9. Referencias

- OWASP Top 10:2025 — https://owasp.org/Top10/2025/
- OWASP ASVS 5.0 — https://owasp.org/www-project-application-security-verification-standard/
- Authentication Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Password Storage Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Credential Stuffing Prevention Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html
- Authorization Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- IDOR Prevention Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- JSON Web Token Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- Session Management Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Índice ASVS ↔ Cheat Sheets — https://cheatsheetseries.owasp.org/IndexASVS.html
