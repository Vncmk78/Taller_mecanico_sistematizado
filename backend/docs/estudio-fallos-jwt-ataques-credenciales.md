# 🛡️ Estudio: fallos del JWT manipulado y ataques de credenciales

**Ámbito:** autenticación del sistema FastAPI vigente — el contrato JWT de
`shared/auth.py`, la emisión en MS1 y las dependencias que lo validan en los
cuatro microservicios.

**Estado:** estudio sobre el código en ejecución. **No introduce cambios de
comportamiento.** Los hallazgos de la sección 5 quedan documentados; las
recomendaciones están pendientes de decisión del equipo.

> **Actualización posterior.** La recomendación **F1** (bloqueo de cuenta) ya se
> implementó en MS1: `C1` pasó de *Abierto* a *Mitigado* y se anota en §4.3.
> `C11` (auditoría de intentos) quedó **descartada por decisión del equipo**:
> se implementó solo contador y bloqueo, sin tabla de registro de intentos.
> También quedó resuelta **F7**: hoy todo `401` lleva `WWW-Authenticate: Bearer`
> (`shared/errores_auth.py`). Los catálogos se actualizaron con la evidencia de
> las suites nuevas; ver §6.

---

## 1. Por qué este estudio

El token es la única credencial que viaja en cada petición protegida. Dos
preguntas definen si el sistema resiste a un atacante con acceso a la red:

1. **¿Se puede manipular un JWT** (cambiar la firma, el algoritmo, los claims)
   para hacerse pasar por otro usuario o escalar privilegios?
2. **¿Se puede atacar la puerta de entrada** (login y registro) para adivinar
   contraseñas o descubrir qué cuentas existen?

Este documento recorre el catálogo habitual de fallos —los que aparecen en las
listas de OWASP y en la práctica de CTF— y los contrasta uno a uno con el código
real, marcando cuáles están mitigados, cuáles siguen abiertos y cuáles no
aplican a esta arquitectura.

> Nota: `backend/ESTUDIO_BCRYPT_Y_VALIDACION.md` cubre el **monolito
> Node/Express deprecado** (bcryptjs, tokens de 24 h). Este estudio cubre el
> sistema FastAPI vigente (`shared/auth.py` + MS1).

---

## 2. Método y alcance

- Se revisó el código productivo: `shared/auth.py`, `services/ms1_auth/*`
  (config, dependencias, router y servicio de autenticación), `security/passwords.py`
  y los guardas de MS2/MS3/MS4.
- Se complementó con **experimentos ejecutados** (sección 6): tokens forjados a
  mano con `alg: none`, payload manipulado sin volver a firmar y medición del
  coste de bcrypt.
- La evidencia de cada fila se ancla a la función que la implementa, no a un
  número de línea (que cambia con el tiempo).

Fuera de alcance: TLS/transporte (ver `estudio-seguridad-transporte.md`),
autorización por recurso y CORS.

---

## 3. Parte A — Fallos comunes del JWT manipulado

### 3.1 El contrato que se ataca

`shared/auth.py` es puro (sin FastAPI ni BD) y concentra la emisión y la
validación. El token tiene **exactamente** tres claims:

```
sub    ->  str(usuario_id)          (entero positivo, como cadena)
roles  ->  ["cliente" | "mecanico" | "administrador", ...]
exp    ->  expiración (UTC)
```

`validar_token_acceso` fija `algorithms=["HS256"]` y pide
`options={"require_exp": True, "require_sub": True}`. Todo lo demás se valida a
mano en `_extraer_usuario_id` y `_extraer_roles`.

### 3.2 Catálogo

| # | Ataque | Estado | Evidencia |
|---|---|---|---|
| J1 | `alg: none` (token sin firma) | ✅ Mitigado | `algorithms=["HS256"]` fijo; probado: `TokenInvalidoError` (§6) y `test_integridad_token_jwt.py` (401 vía HTTP) |
| J2 | Confusión RS256 → HS256 | ✅ No aplica | Solo HS256 simétrico; no existe clave pública que usar como secreto |
| J3 | Firma inválida (firmar con otra clave) | ✅ Mitigado | HMAC verificado por `jwt.decode`; `test_jwt.py`, `test_seguridad_autenticacion.py`, `test_integridad_token_jwt.py` (firma alterada y payload alterado sin re-firmar) |
| J4 | Secreto débil / fuerza bruta del HMAC | ⚠️ Parcial | `_validar_configuracion` exige ≥32 caracteres y `SecretStr` sin default; **no garantiza 256 bits de entropía** |
| J5 | Token eterno (sin `exp`) | ✅ Mitigado | `options={"require_exp": True}`; `JWT_EXPIRE_MINUTES = 60`; `test_integridad_token_jwt.py[sin-exp]` |
| J6 | Token sin `sub` | ✅ Mitigado | `options={"require_sub": True}` + `_extraer_usuario_id`; `test_integridad_token_jwt.py[sin-sub]` |
| J7 | `sub` manipulado o no numérico (`"usr_1"`) | ✅ Mitigado | `_extraer_usuario_id` exige cadena decimal positiva |
| J8 | `roles` manipulado / desconocido / duplicado / vacío | ✅ Mitigado | No se altera sin la firma; `_extraer_roles` valida los cuatro casos; `test_integridad_token_jwt.py[sin-roles]` y el payload reescrito sin re-firmar |
| J9 | Inyección de cabecera `kid` / `jku` / `x5u` | ✅ No aplica | La clave se pasa directa; no hay resolución remota ni uso de `kid` |
| J10 | Repetición de un token robado (sin `jti`, sin revocación) | ⚠️ Abierto | No hay `jti` ni lista de revocación; el token sirve hasta `exp` (≤60 min) |
| J11 | Autorización obsoleta (roles congelados en el token) | ⚠️ Abierto | Los guardas leen los roles **del token**; retirar un rol no surte efecto hasta que expire |
| J12 | Secreto compartido por los cuatro servicios | ⚠️ Riesgo de diseño | `.env.example`: *«Misma clave en MS1, MS2, MS3 y MS4»* |
| J13 | Token en logs / URL / consola | ✅ Mitigado | La Gateway no registra cabeceras ni cuerpos; `ErrorBoundary` corregido (`estudio-seguridad-transporte.md` §7.5) |
| J14 | Claims `iss`/`aud` ausentes | ✅ No aplica | Un solo dominio de confianza; no hay varios emisores que distinguir |
| J15 | Desfase de reloj (*clock skew*) | ℹ️ Menor | `jose` sin `leeway`; solo afecta a tokens en el borde exacto de expiración |

### 3.3 Lectura de los resultados

**Lo que está bien resuelto y por qué importa.** Los tres ataques clásicos de
manipulación (J1, J3, J7/J8) están cerrados por dos decisiones concretas:

- **Algoritmo fijado, nunca negociado.** `validar_token_acceso` pasa
  `algorithms=["HS256"]` explícito. Un atacante no puede pedir `none` ni forzar
  otro algoritmo: `jwt.decode` compara `alg` contra esa lista y rechaza. Lo
  verifiqué con un token sin firma construido a mano → `TokenInvalidoError`.
- **Firma sobre todo el token.** Cambiar el `roles` de `cliente` a
  `administrador` en el payload invalida el HMAC. Repetí el caso forjando el
  payload sin refirmar → `TokenInvalidoError`.

**J2 no aplica hoy, pero es una trampa si se migra.** La confusión RS256→HS256
solo existe cuando el servidor verifica con clave **pública** y el atacante firma
con esa misma cadena pública como si fuera el secreto HMAC. Aquí no hay clave
pública. Si algún día se migra a firma asimétrica (J12), **hay que seguir
fijando un único algoritmo**, o el fallo aparece.

**J4 es una mitigación, no una garantía.** `_validar_configuracion` rechaza
claves de menos de 32 caracteres, pero 32 caracteres de texto no equivalen a 256
bits de entropía. El valor correcto es el que sugiere `.env.example`:
`secrets.token_urlsafe(48)`. El punto fuerte real es que el secreto **solo**
proviene del entorno (`SecretStr`, sin default) y nunca del código.

### 3.4 Los tres fallos que quedan abiertos

**J10 — un token robado es válido hasta que expira.** No hay `jti` ni lista de
revocación; cerrar sesión en el cliente no invalida el token en el servidor. Con
`exp` de 60 minutos, la ventana de abuso de un token filtrado es de hasta una
hora.

**J11 — la autorización va con retraso.** `requerir_roles` (MS1/MS3),
`resolver_cliente_actual` (MS2) y los filtros de visibilidad deciden con los
roles **del token**, que se emitieron en el login. Si a un usuario se le retira
el rol `administrador`, su token seguirá siendo válido como administrador hasta
por 60 minutos. (La excepción es `/auth/me`, que relee el usuario de la base y
por eso refleja los roles vigentes.) Es el mismo hallazgo que registra
`estudio-rbac-multiples-roles.md` al hablar de «versión de rol embebida en el
token o revalidación por petición».

**J12 — el secreto se comparte entre los cuatro servicios.** Está documentado a
propósito en `.env.example` (*«Misma clave en MS1, MS2, MS3 y MS4»*): es lo que
permite que MS1 emita y MS2/MS3/MS4 validen sin hablar entre sí (SSO sin acoplar
bases). El precio es que el secreto vive en el entorno de cada servicio: quien
lea el entorno de cualquiera de ellos puede forjar tokens que **todos**
aceptarán. La Gateway, en cambio, no lo tiene, y por eso es estructuralmente
incapaz de falsificar una identidad.

---

## 4. Parte B — Ataques de credenciales

### 4.1 El flujo que se ataca

```
POST /auth/register  ->  valida formato, ¿correo libre? -> bcrypt.hash -> BD
POST /auth/login     ->  busca por correo -> ¿activo? -> bcrypt.checkpw -> emite JWT
```

`autenticar_usuario` (MS1) es el corazón:

```python
if (usuario is None
        or not usuario.activo
        or not verificar_contrasena(contrasena, usuario.contrasena_hash)):
    raise CredencialesInvalidasError("Correo o contraseña incorrectos")
```

### 4.2 Catálogo

| # | Ataque | Estado | Evidencia |
|---|---|---|---|
| C1 | Fuerza bruta en línea contra una cuenta | ✅ Mitigado | Bloqueo por cuenta en `/auth/login`: tras `MS1_LOGIN_MAX_INTENTOS` (5) fallos la cuenta queda bloqueada `MS1_LOGIN_BLOQUEO_MINUTOS` (15) min y responde `429` + `Retry-After`; `test_login_intentos_fallidos.py` |
| C2 | *Credential stuffing* / *password spraying* | ⚠️ Abierto | Sin límite por IP, sin MFA, sin captcha |
| C3 | Enumeración de usuarios por el **mensaje** de login | ✅ Mitigado | Mismo `401` y mismo detalle para correo inexistente, contraseña incorrecta y cuenta inactiva |
| C4 | Enumeración de usuarios por el **tiempo** de login | ⚠️ Abierto | El cortocircuito del `if` evita bcrypt cuando el correo no existe o está inactivo |
| C5 | Enumeración de usuarios por el **registro** | ⚠️ Abierto | `POST /auth/register` responde `409` «El correo ya está registrado» |
| C6 | Almacenamiento de contraseñas | ✅ Mitigado | bcrypt con sal por contraseña (`bcrypt.gensalt()`), coste 12; nunca texto plano |
| C7 | Truncamiento de bcrypt a 72 bytes | ✅ Mitigado | `hash_contrasena` rechaza >72 bytes; `verificar_contrasena` devuelve `False` ante error |
| C8 | Política de contraseña débil | ⚠️ Parcial | Solo `min_length=8`, sin requisitos de complejidad |
| C9 | El registro elige el rol (escalada) | ✅ Mitigado | `extra="forbid"`; el rol `cliente` lo asigna el servidor (`test_auth_api.py`) |
| C10 | Contraseña o hash en respuesta o logs | ✅ Mitigado | `UsuarioRespuesta` no incluye el hash; no se registran credenciales |
| C11 | Detección de ataques (log de intentos fallidos) | ⚠️ Descartado | **Decisión del equipo:** solo contador y bloqueo (C1), sin tabla de auditoría de intentos |
| C12 | Segundo factor (MFA) | ⚠️ Ausente | No implementado |
| C13 | Recuperación de contraseña | ℹ️ No existe | Sin flujo, así que tampoco hay vectores de *reset* que atacar |

### 4.3 Lo que sí está resuelto

**C1 — la cuenta se bloquea tras los intentos fallidos.** `/auth/login` cuenta
los fallos **por cuenta** en la propia fila del usuario (`intentos_fallidos`,
`bloqueado_hasta`). Al llegar a `MS1_LOGIN_MAX_INTENTOS` (5 por defecto) la
cuenta se bloquea durante `MS1_LOGIN_BLOQUEO_MINUTOS` (15 min) y el intento
siguiente responde `429` con `Retry-After` en segundos. El bloqueo se verifica
**antes** de pagar el `bcrypt.checkpw`, así que no se puede usar para forzar
coste de CPU. Un login correcto reinicia el contador, y un bloqueo vencido
también, para no re-bloquear al primer fallo tras esperar. Ver `config.py`,
`services/autenticacion.py` y `tests/test_login_intentos_fallidos.py`.
Quedan fuera el límite por IP y la auditoría de intentos (C2, C11).

**C3 — no se filtra por el mensaje.** Los tres desenlaces (correo inexistente,
contraseña incorrecta, cuenta desactivada) producen el **mismo** `401` con el
mismo texto. Es la defensa correcta contra la enumeración por mensaje y coincide
con la buena práctica que ya describía `ESTUDIO_BCRYPT_Y_VALIDACION.md` §5.

**C6/C7 — el almacenamiento es sólido.** bcrypt con sal aleatoria por contraseña
y coste 12 (verificado). El coste es lo que encarece cada intento de fuerza
bruta: medí ~0,9 s por `checkpw` en esta máquina (el coste nominal de 12 ronda
las centenas de milisegundos; la máquina estaba cargada). El rechazo explícito
de contraseñas de más de 72 bytes elimina el clásico fallo de truncamiento, en
el que dos contraseñas distintas largas colisionan.

**C9 — el registro no permite elegir el rol.** El esquema prohíbe campos extra y
el rol `cliente` lo decide el servidor, así que el self-service no es una vía de
escalada.

### 4.4 El fallo más sutil: el oráculo temporal del login (C4)

El mensaje es uniforme (C3), pero el **tiempo de respuesta no lo es**. El `if`
de `autenticar_usuario` usa `or`, y Python evaluá de izquierda a derecha con
cortocircuito: si `usuario is None` (correo no registrado) o `not usuario.activo`
(cuenta desactivada), **no se llega a ejecutar `verificar_contrasena`**. En esos
dos casos la respuesta vuelve prácticamente sin coste de bcrypt; cuando el correo
sí existe, se paga el `checkpw` completo.

Resultado: un atacante puede distinguir «correo no registrado» de «contraseña
incorrecta» midiendo el tiempo, aunque el cuerpo de la respuesta sea idéntico. La
misma técnica delata si una cuenta existe pero está desactivada. Es una
enumeración de cuentas de segundo orden: no se ve en el mensaje, se ve en el
reloj.

### 4.5 El registro sí enumera por su respuesta (C5)

A diferencia del login, `POST /auth/register` responde `409 Conflict` con «El
correo ya está registrado». Eso convierte el propio formulario de alta en un
oráculo de existencia de cuentas: probando correos se sabe quién está registrado.
Es un *trade-off* de experiencia de usuario evidente (el formulario debe poder
decir «ese correo ya existe»), pero conviene tenerlo presente: la protección de
C3 se anula si el atacante puede usar el registro para lo mismo.

---

## 5. Hallazgos y recomendaciones

Estas recomendaciones nacieron de un estudio, no de una tarea de corrección, y
varias son decisiones de producto, no defectos puntuales. **F1 y F7 ya se
aplicaron** (ver §4.3 y §6); el resto se deja documentado, pendiente de decisión
del equipo.

> **F1 se implementó después** (ver actualización en la cabecera y §4.3). Las
> demás siguen pendientes de decisión del equipo.

**F1 — Sin límite de intentos ni bloqueo (C1, C2, C11). ✅ Implementado (parcial).**
El sistema permitía intentos ilimitados de login. *Implementado:* bloqueo **por
cuenta** en MS1 con umbral y duración configurables, respuesta `429` +
`Retry-After`, y bloqueo verificado antes de bcrypt (`§4.3`). *Pendiente:* el
límite por IP y la auditoría de intentos (C2, C11) — esta última **descartada
por decisión del equipo**. Es la misma brecha que ya listaba
`ESTUDIO_BCRYPT_Y_VALIDACION.md` §9.

**F2 — Oráculo temporal en el login (C4).**
*Recomendación:* cuando el correo no exista o la cuenta esté inactiva, verificar
la contraseña igualmente contra un **hash señuelo** (precalculado una vez), de
modo que el coste de respuesta sea constante. Es un cambio pequeño y localizado
en `autenticar_usuario`.

**F3 — Enumeración por el registro (C5).**
*Recomendación:* decidir el *trade-off*. Mantener el `409` es cómodo para el
usuario; si se prioriza no filtrar la existencia de cuentas, la alternativa es
responder de forma genérica y confirmar por correo.

**F4 — Repetición de token y autorización obsoleta (J10, J11).**
*Recomendación:* un claim de versión de token por usuario o un `jti` con lista de
revocación, para poder invalidar sesiones y aplicar cambios de rol al instante;
mientras tanto, acortar `JWT_EXPIRE_MINUTES` reduce la ventana. Para operaciones
sensibles, revalidar el rol contra la base en lugar de confiar solo en el token.

**F5 — Secreto compartido y HMAC simétrico (J4, J12).**
*Recomendación:* migrar a firma **asimétrica** (RS256/EdDSA): MS1 firma con la
clave privada y el resto valida con la pública. Así, un microservicio de solo
lectura no puede emitir tokens y el secreto de firma vive en un único sitio. Si
se mantiene HS256, rotar la clave periódicamente y generarla con
`secrets.token_urlsafe(48)`.

**F6 — Política de contraseña y MFA (C8, C12).**
*Recomendación:* subir el mínimo (longitud y, si se quiere, complejidad) y, para
las cuentas administrativas, exigir segundo factor.

**F7 — Detalle menor: el `401` del login no lleva `WWW-Authenticate`
(observación). ✅ Resuelto.**
El `401` de `/auth/login` se lanzaba sin la cabecera `WWW-Authenticate`. Hoy
todos los `401` salen por `shared/errores_auth.py::error_no_autenticado`, que
añade `WWW-Authenticate: Bearer` (RFC 9110), incluido el del login; el helper
antiguo `_error_no_autenticado` de cada servicio ya no existe. La uniformidad
del cuerpo y de la cabecera está probada en `tests/test_normalizacion_401_403.py`
y `tests/test_integridad_token_jwt.py`.

---

## 6. Cómo se verificó

**Pruebas de la suite** (todas verdes tras este estudio):

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest \
  tests/test_jwt.py tests/test_seguridad_autenticacion.py \
  tests/test_autorizacion.py tests/test_auth_api.py -q
```

Estas suites cubren la parte mitigada del catálogo: firma inválida, token
expirado, `sub` no numérico, roles inválidos, token de usuario inexistente o
inactivo y `401`/`403` de los guardas.

Tras la implementación de F1 y la normalización de respuestas, se añaden:

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest \
  tests/test_login_intentos_fallidos.py tests/test_integridad_token_jwt.py \
  tests/test_normalizacion_401_403.py -q
```

| Suite | Qué cubre |
|---|---|
| `test_login_intentos_fallidos.py` | C1: `429` + `Retry-After` tras el umbral, y reinicio del contador al acertar |
| `test_integridad_token_jwt.py` | J1, J3, J5–J8 a nivel HTTP: firma alterada, payload alterado sin re-firmar, `sub`/`exp`/`roles` ausentes, malformado y `alg: none` |
| `test_normalizacion_401_403.py` | F7: cuerpo y cabecera uniformes en todos los `401`/`403` |

**Experimentos ejecutados** (ad-hoc, no forman parte de la suite):

| Comprobación | Resultado |
|---|---|
| Token `alg: none` construido a mano → `validar_token_acceso` | `TokenInvalidoError` |
| Token HS256 válido con el `roles` reescrito sin refirmar | `TokenInvalidoError` |
| Prefijo del hash generado por `bcrypt.gensalt()` | `$2b$12$` (coste 12) |
| Tiempo de `bcrypt.checkpw` en esta máquina | ~0,9 s (máquina cargada) |

---

## 7. Referencias

- OWASP — JSON Web Token for Java Cheat Sheet (catálogo de ataques JWT).
- OWASP — Authentication Cheat Sheet (enumeración, fuerza bruta, almacenamiento).
- RFC 9110 §15.5.2 — `WWW-Authenticate` en respuestas `401`.
- `estudio-seguridad-transporte.md` — superficie de ataque y contrato del token.
- `estudio-rbac-multiples-roles.md` — roles congelados en el token.
