# Estudio: diagnóstico de fallos de sesión y propagación de tokens

**Ámbito:** la sesión JWT del sistema FastAPI vigente — su ciclo de vida, los
saltos que da el token entre cliente, Gateway y microservicios (incluidas las
llamadas servicio→servicio) y el síntoma exacto con el que cada fallo llega al
cliente, para poder diagnosticarlo sin adivinar.

**Estado:** estudio sobre el código en ejecución. **No implementa cambios.**
Construye el mapa *síntoma → causa → dónde confirmar* y deja los hallazgos de
la sección 7 documentados, pendientes de decisión del equipo.

---

## 1. Por qué este estudio

Un fallo de sesión no siempre aparece donde nace. El token se valida en cada
salto con la misma clave (`shared/auth.py`), pero los saltos internos entre
microservicios **no propagan el rechazo tal cual**: lo convierten en `503`
antes de responder. Quien depura viendo solo el estado HTTP final puede
atribuir al servicio equivocado un problema que nació en la sesión.

Dos preguntas definen el estudio:

1. ¿Qué puede fallar en una sesión y con qué síntoma lo ve el cliente?
2. ¿Por dónde viaja el token, con qué contrato, y qué herramientas hay para
   seguir una petición de punta a punta?

---

## 2. Alcance y método

- Se revisó el código productivo: `shared/auth.py`, `shared/errores_auth.py`,
  `gateway/{middleware,routers/proxy,cliente_http,errores,rutas}.py` y las
  integraciones `ms2_taller/integracion_ms1.py`, `ms2_taller/integracion_ms3.py`,
  `ms3_presupuestos/integracion_ms2.py`, `ms4_evidencias/integracion_ms2.py`,
  `ms4_evidencias/integracion_ms3.py`, más los guards de cada servicio
  (`dependencies.py`) y el router de login de MS1.
- La evidencia se ancla a archivo y función, no a números de línea.

Complementa, sin repetir, a los estudios vecinos:

| Documento | Qué cubre que acá no |
|---|---|
| `estudio-fallos-jwt-ataques-credenciales.md` | ataques al token y a las credenciales (J1–J15, C1–C13) |
| `estudio-httpx-proxy.md` | decisiones de proxy y timeouts de la Gateway |
| `estudio-rbac-multiples-roles.md` | el diseño RBAC y la vigencia de los roles (§6) |
| `pruebas-comunicacion-gateway.md` | cómo levantar todo y verificar los contratos en vivo |

---

## 3. El ciclo de vida de la sesión

La sesión es **un JWT sin estado en el servidor**: lo emite MS1 en el login,
vive exactamente `MS1_JWT_EXPIRE_MINUTES` (60 min por defecto) y no existe ni
`logout`, ni `refresh`, ni revocación (ver J10/J11 del estudio de fallos JWT).

| Momento | Qué ocurre | Cómo se manifiesta |
|---|---|---|
| Login correcto | `autenticar_usuario` valida, `crear_token_acceso` firma | `200` con `access_token` (claims `sub`, `roles`, `exp`) |
| Login con cuerpo vacío o espacios | rechazo en la capa de schemas (`min_length=1`) | `422`, no cuenta intento ni bloquea |
| Login con credenciales incorrectas, correo inexistente o **cuenta inactiva** | mismo camino de error genérico | `401` idéntico en los tres casos |
| Login de cuenta bloqueada (≥`LOGIN_MAX_INTENTOS` fallos) | `CuentaBloqueadaError` | `429` + `Retry-After` en segundos |
| Login de cuenta **sin roles** | credenciales correctas, pero no hay token emitible | `403` |
| Uso del token | cada servicio valida firma y expiración localmente | `401` uniforme si falla (ver §5) |
| Expiración (60 min) | `require_exp` de `validar_token_acceso` | `401` idéntico al de un token inválido |
| Cuenta desactivada **después** del login | solo `/auth/me` relee la base (`obtener_usuario_actual`) | `/auth/me` → `401`; MS2/MS3/MS4 siguen aceptando el token hasta que expire |
| Rol retirado **después** del login | los guards leen los roles del token | el privilegio sobrevive hasta la expiración; `/auth/me` refleja los roles vigentes |

Detalle propio de MS2: la sesión puede estar sana y aun así fallar la
resolución del perfil: `resolver_cliente_actual` responde `404` («El usuario
autenticado no tiene un perfil Cliente en MS2») cuando el `usuario_id` del
token nunca creó vehículo (y por tanto perfil) en MS2. No es un fallo del
token; es un `404` de perfil.

---

## 4. Los saltos del token

### 4.1 Cliente → Gateway

La Gateway **no valida el JWT**: no tiene la clave (riesgo J12 del estudio de
JWT) y por eso es estructuralmente incapaz de falsificar identidades. El proxy
(`gateway/routers/proxy.py`) reenvía la cabecera `Authorization` tal cual —no
está en `_CABECERAS_PROHIBIDAS`— y añade trazabilidad:

- `x-request-id`: el que trae el cliente si es válido, o un UUID nuevo
  (`RequestIdMiddleware`);
- `x-forwarded-for` / `x-forwarded-proto` / `x-forwarded-host`.

### 4.2 Gateway → microservicio

El primer segmento de la ruta elige el servicio (`gateway/rutas.py`:
`auth`→MS1, `vehiculos`/`ordenes`/…→MS2, `presupuestos`/…→MS3,
`evidencias`→MS4). Cada microservicio valida el Bearer con
`shared/auth.validar_token_acceso` **y su propia copia de la clave** (la
misma en el `.env` de los cuatro). De vuelta, el proxy:

- deja pasar `401`/`403` **con cuerpo JSON tal cual** (incluida la cabecera
  `WWW-Authenticate: Bearer` y `Retry-After`);
- normaliza al catálogo propio solo los errores sin JSON, conservando esas
  dos cabeceras;
- traduce sus propios fallos de red a `502` `MICROSERVICIO_INALCANZABLE`,
  `503` `GATEWAY_SATURADA`, `504` `TIEMPO_AGOTADO` (`gateway/errores.py`).

### 4.3 Microservicio → microservicio (delegación pura)

Los saltos internos **reenvían el MISMO JWT del usuario final**: no hay token
de servicio ni cuentas técnicas. La visibilidad la decide siempre el dueño del
token en el servicio que posee el dato (verificadores en cada
`integracion_ms*.py`; el token llega por `obtener_token_bearer`, que exige la
sesión antes de reenviarla).

| Quién llama | Destino | Llamada | Token reenviado | Cuándo |
|---|---|---|---|---|
| MS2 | MS1 | `GET /auth/usuarios/{id}` | el del administrador que asigna | asignar/reasignar mecánico (§4.3 matriz) |
| MS2 | MS3 | `GET /presupuestos/decisiones/{id}` | el del cliente que decide | aplicar la primera decisión en la orden (SCRUM-438) |
| MS3 | MS2 | `GET /ordenes/{id}` y `?solo_propietario=true` | el del usuario que opera | crear/versionar presupuestos y registrar stock (§4.4) |
| MS3 | MS2 | `POST /ordenes/{id}/decisiones-presupuesto` | el del cliente que decide | primera decisión de presupuesto (SCRUM-438) |
| MS4 | MS2 | `GET /ordenes/{id}` | el del usuario que sube/consulta | asociar evidencias a la orden (§4.5) |
| MS4 | MS3 | `GET /presupuestos/{id}` | el del mecánico/administrador | evidencia de contexto presupuesto |

Los cinco clientes internos usan timeout propio (`MS*_TIMEOUT_SEGUNDOS`,
3 s por defecto), sin reintentos ni *circuit breaker* — la Gateway sí reintenta
una vez la conexión; los saltos internos no.

### 4.4 El contrato fail-closed de los saltos internos

Todos los verificadores comparten el mismo contrato (p. ej.
`VerificadorOrdenesHttp._verificar`):

| Respuesta del destino | Traducción del verificador | Estado al cliente |
|---|---|---|
| `200` | visible / válido | continúa el caso de uso |
| `403` / `404` | *NoVisible* (no existe o es ajeno) | `404` indistinguible (no enumera) |
| cualquier otro (incluido `401`), error de red o timeout | *ServicioNoDisponible* | `503` |

Casos particulares del contrato:

- **MS3→MS2 `verificar_propiedad`**: exige además la cabecera
  `X-Orden-Propiedad-Verificada: true` de MS2; sin confirmación explícita,
  resuelve `503` («MS2 no confirmó la verificación de propiedad»). Es la
  defensa contra un MS2 de versión antigua que ignore el query
  `solo_propietario=true`.
- **MS2→MS3**: un `409` del destino se traduce a *NoAplicable* (decisión
  histórica sin stock evaluable), el resto sigue la tabla.
- **SCRUM-438 (MS3)**: si la decisión quedó registrada pero el efecto en MS2
  no se confirmó, `DecisionAplicacionPendienteError` responde `503` con el
  hecho persistido y un reintento idempotente
  (`POST /api/presupuestos/decisiones/{id}/aplicacion`) — no duplica la
  decisión ni exige volver a aprobar.

---

## 5. Catálogo de fallos y su diagnóstico

Qué ve el cliente, qué puede estar pasando y dónde confirmarlo:

| Síntoma | Causas posibles | Dónde confirmar |
|---|---|---|
| `401` `{"detail": "No autenticado"}` + `WWW-Authenticate: Bearer` | token ausente, cabecera mal formada, firma inválida, **expirado**; en `/auth/me` también usuario borrado o desactivado | uniforme por diseño (`errores_auth.py`): el cuerpo no distingue la causa; ver §6 para el rastro |
| `403` `{"detail": "No tienes permiso..."}` | rol insuficiente para el endpoint (matriz §4) o **rol retirado después del login** (token congelado) | `matriz-autorizacion-roles.md`; `/auth/me` muestra los roles vigentes |
| `404` «Orden/Presupuesto no encontrada» y afines | recurso inexistente, **recurso ajeno al rol** (indistinguible por diseño) o —solo MS2— perfil Cliente inexistente para un usuario_id válido | el `404` nunca revela cuál de las tres es; es intencional |
| `429` + `Retry-After` | cuenta bloqueada por intentos fallidos en el login | MS1: `intentos_fallidos`/`bloqueado_hasta` en la fila del usuario |
| `403` en el login («no tiene roles») | credenciales correctas pero la cuenta no tiene roles: no hay token emitible | MS1: tabla `usuario_rol` |
| `422` en el login | credenciales vacías o de espacios (schemas) | no llega al caso de uso; no bloquea |
| `503` «No fue posible validar…» desde MS2/MS3/MS4 | la dependencia está caída, **o** el timeout de 3 s venció, **o** la dependencia **rechazó el token** (claves desincronizadas entre servicios): el `401` interno se convierte en `503` (§4.4) | ver §6 y hallazgo H1: el estado final no distingue las tres causas |
| `503` con `DecisionAplicacionPendiente` | MS3 registró la decisión pero MS2 no confirmó el efecto | el cuerpo trae `decision_id` y la ruta de reintento idempotente |
| `502`/`503`/`504` con `error.codigo` de la Gateway | fallo de red Gateway→MS (`MICROSERVICIO_INALCANZABLE`, `GATEWAY_SATURADA`, `TIEMPO_AGOTADO`) | el catálogo de `gateway/errores.py` sí distingue la causa de red |

Lectura del catálogo: **la única familia de fallos que el cliente ve con
detalle diagnóstico es la de la propia Gateway** (código de catálogo); todo lo
que ocurre dentro de los microservicios llega deliberadamente uniforme
(`401`/`403`/`404`/`503`) para no filtrar información.

---

## 6. Herramientas de diagnóstico que ya existen

- **`X-Request-ID`**: la Gateway lo respeta o lo genera
  (`RequestIdMiddleware`), lo reenvía al microservicio y lo devuelve en la
  respuesta. MS4 lo registra en **todos** sus eventos
  (`services/ms4_evidencias/services/registro.py`), así que una subida puede
  seguirse de la Gateway hasta MS4. MS1, MS2 y MS3 **no lo registran**
  (hallazgo H2).
- **Logs estructurados de MS4**: una línea `clave=valor` por evento, con
  lista blanca de campos (nunca el JWT, ni URLs prefirmadas, ni el nombre del
  archivo), p. ej. `evento=acceso_rechazado motivo=orden_no_visible` y
  `evento=dependencia_no_disponible servicio=ms2 error=ConnectError`.
- **Catálogo de errores de la Gateway**: todo error generado por la Gateway
  lleva `error.codigo` + `request_id` en el cuerpo y en `X-Request-ID`.
- **Cabeceras con semántica**: `WWW-Authenticate: Bearer` en todo `401`
  (RFC 9110), `Retry-After` en el `429` de bloqueo — ambas conservadas por el
  proxy incluso al normalizar errores sin JSON.
- **`/health`** de la Gateway y de cada microservicio, y el procedimiento de
  `pruebas-comunicacion-gateway.md` para levantar la cadena completa y
  verificar los contratos con datos de prueba.

---

## 7. Hallazgos

Ninguno se corrige en este estudio; quedan documentados para decisión.

**H1 — El `401` interno nunca llega como `401`.** Si el token es rechazado por
el servicio llamado en un salto interno (p. ej. las claves difieren entre dos
`.env`), el verificador lo trata como «otro estado» y el cliente recibe `503`
«No fue posible validar…». La decisión fail-closed es correcta — no revela el
motivo del rechazo —, pero hace **ambigua** la distinción entre «dependencia
caída» y «token rechazado»: los dos síntomas son idénticos y solo se separan
mirando los logs del servicio llamado o reproduciendo el salto a mano.
*Recomendación (no aplicada):* registrar el estado HTTP real del destino en el
punto de la llamada (en el log, no en la respuesta).

**H2 — El rastro de `request_id` se pierde en 3 de 5 nodos.** La Gateway lo
genera y reenvía, MS4 lo registra; MS1, MS2 y MS3 lo reciben pero no lo
loguean. Un fallo que atraviesa MS2 o MS3 no se puede correlacionar hoy por
identificador de petición. *Recomendación (no aplicada):* un middleware de log
mínimo (método, ruta, estado, `request_id`) en los tres servicios, con la
misma disciplina de MS4 (sin cabeceras ni tokens).

**H3 — MS4 no registra el código HTTP del destino.** En
`dependencia_no_disponible`, MS4 guarda el **tipo** de la excepción de red
(`error=ConnectError`) pero no el estado HTTP cuando la dependencia respondió
mal (incluye el caso de H1). Con H1 y H3 juntos, la causa raíz de un `503`
cascada queda fuera de todos los logs.

**H4 — Expiración sin refresh y sin aviso.** La sesión muere a los 60 min sin
mecanismo de renovación ni `exp` negociable con el cliente. El `401`
resultante es indistinguible del de un token manipulado (por diseño,
`errores_auth.py` no distingue causas): el cliente no puede saber si debe
re-login o si su almacenamiento de token corrompió la credencial.

**H5 — La desactivación de cuenta solo la ve `/auth/me`.** Un usuario
desactivado después del login sigue operando MS2/MS3/MS4 hasta que el token
expire, porque los guards no consultan la base de MS1. Es la consecuencia
operativa del hallazgo J11/§6 de `estudio-rbac-multiples-roles.md`; la ventana
es de hasta 60 minutos.

**H6 — Los roles congelados afectan también a los saltos internos.** Como el
salto MS→MS reenvía el MISMO token, un rol retirado tras el login sigue
autorizando toda la cadena (p. ej. MS2→MS1 valida el destino de la asignación
con el token «administrador» del asignante aunque el rol ya se haya retirado
en la base). Agravante operativo de J11.

**H7 — Timeouts internos fijos y sin reintento.** Los cinco clientes internos
usan 3 s sin reintentos ni *circuit breaker*; la Gateway sí reintenta la
conexión una vez. Un MS lento (no caído) se manifiesta igual que uno caído:
`503`. Los valores son configurables (`MS*_TIMEOUT_SEGUNDOS`), pero hoy no
hay métricas de latencia por salto para afinarlos.

---

## 8. Cómo se verificó

Comportamientos descritos cubiertos por la suite (rama `DerisA`, todos en
verde al momento del estudio):

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_integracion_jwt_gateway_ms2.py \
  tests/test_seguridad_autenticacion.py tests/test_normalizacion_401_403.py \
  tests/test_autenticacion_canales.py tests/test_ms4_autorizacion_evidencias.py \
  tests/test_ms4_logs.py tests/test_ms3_integracion_ms2.py \
  tests/test_ms2_integracion_ms3.py tests/test_acceso_indebido_roles.py \
  tests/test_gateway_errores_proxy.py -q
```

| Suite | Qué verifica de este estudio |
|---|---|
| `test_integracion_jwt_gateway_ms2.py` | el salto completo real MS1→Gateway→MS2 con el mismo JWT (SCRUM-358) |
| `test_seguridad_autenticacion.py` | token expirado, firmado con otra clave, usuario inexistente/inactivo, cabeceras mal formadas |
| `test_normalizacion_401_403.py` | la forma uniforme del `401`/`403` en los cuatro servicios |
| `test_autenticacion_canales.py` | login y uso del Bearer desde web y móvil vía Gateway |
| `test_ms4_autorizacion_evidencias.py` | MS4 consulta MS2 con el MISMO JWT (§4.3 de este estudio) |
| `test_ms4_logs.py` | eventos estructurados con `request_id` y lista blanca (sin JWT) |
| `test_ms3_integracion_ms2.py` / `test_ms2_integracion_ms3.py` | el contrato fail-closed de los saltos y la coordinación SCRUM-438 |
| `test_acceso_indebido_roles.py` | `503` al caer la dependencia y `404` indistinguible en recursos ajenos |
| `test_gateway_errores_proxy.py` | catálogo `502`/`503`/`504` y conservación de `WWW-Authenticate`/`Retry-After` |

---

## 9. Referencias

- `matriz-autorizacion-roles.md` — quién puede hacer qué (§4 manda sobre la
  autorización por recurso).
- `estudio-fallos-jwt-ataques-credenciales.md` — J10/J11 (repetición y roles
  congelados) y F4 (recomendación de revocación).
- `estudio-rbac-multiples-roles.md` §6 — vigencia de los roles y ventana de
  revocación tardía.
- `estudio-httpx-proxy.md` — decisiones de proxy, fases de timeout y reintentos
  de la Gateway.
- `pruebas-comunicacion-gateway.md` — cómo levantar los cuatro servicios y la
  Gateway y verificar los contratos en vivo.
