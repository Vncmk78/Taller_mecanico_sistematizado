# 🛡️ Estudio: Seguridad de la capa de transporte y contratos compartidos

**Ámbito:** CORS, esquemas de seguridad en OpenAPI y dependencias reutilizables
de FastAPI.

**Estado:** estudio sobre el código en ejecución. No introduce cambios de
comportamiento; las recomendaciones de la sección 7 están pendientes de decisión
del equipo.

---

## 1. Por qué este estudio

La Gateway es la única puerta de entrada al backend, así que concentra las tres
decisiones que definen el perímetro del navegador:

1. qué orígenes puede invocar la API (**CORS**),
2. cómo se documenta el token en el Swagger (**OpenAPI security schemes**),
3. qué dependencias de FastAPI resuelven la identidad en cada microservicio
   (**dependencias reutilizables**).

Revisarlas juntas evita el error clásico: proteger bien el servidor pero
documentar mal la API, o validar el token cinco veces con cinco copias
distintas del mismo código.

---

## 2. CORS: qué está configurado y por qué

### 2.1 Dónde vive

La configuración está en `gateway/config.py`, con prefijo de entorno
`GATEWAY_`, y se aplica en `gateway/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
```

### 2.2 Valores por defecto

| Variable | Por defecto | Para qué |
|---|---|---|
| `GATEWAY_CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:8000"]` | Frontend web de Vite (5173) y la propia Gateway (8000, para el healthcheck y Swagger) |
| `GATEWAY_CORS_ORIGIN_REGEX` | `https://[a-z0-9-]+\.vercel\.app` | Previews de despliegue en Vercel |
| `GATEWAY_CORS_ALLOW_CREDENTIALS` | `True` | Permite enviar cookies de sesión |
| Métodos | `*` | `GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD` |
| Cabeceras | `*` | Incluye `Authorization` y `X-Request-ID` |
| Cabeceras expuestas | `X-Request-ID` | El frontend puede correlacionar una petición con los logs |

`CORS_ORIGINS` acepta JSON (`["http://a","http://b"]`) o una lista separada por
comas, normalizado en un `field_validator`.

### 2.3 Decisiones correctas y por qué importan

**`allow_credentials=True` exige `allow_origins` explícito, nunca `*`.** Con
credenciales, el navegador rechaza el origen comodín. Por eso la lista es
explícita y los previews de Vercel se resuelven con una regex acotada
(`[a-z0-9-]+`) en lugar de `allow_origins=["*"]`, que sería inseguro y además
rompería con `credentials`.

**La regex de Vercel está anclada a `https://`.** No admite
`http://` ni comodines de dominio, de modo que un atacante no puede registrar un
`vercel.app` malicioso con HTTP plano.

**`expose_headers=["X-Request-ID"]` es una decisión de operabilidad:** sin ella,
JavaScript no puede leer la cabecera y el frontend no puede mostrar el id de
correlación al reportar un error.

**El middleware de errores va por dentro de CORS.** El orden en `main.py` es
`RequestId` (más externo) → `CORS` → `ManejoErrores` (más interno). Si el
manejador de `500` corriera por fuera de CORS, su respuesta saldría sin
`Access-Control-Allow-Origin` y el navegador la mostraría como error de red en
lugar de un `500` legible. Es una razón no obvia para ese orden.

### 2.4 Lo que CORS no protege

CORS lo aplica **el navegador**, no el servidor. `curl`, Postman o un script
pueden llamar a la Gateway desde cualquier origen. Por eso CORS no es un
mecanismo de autorización: la autorización real es el `401`/`403` del
microservicio, descrita en la sección 5.

---

## 3. Esquemas de seguridad en OpenAPI

### 3.1 Qué declara cada aplicación

Verificado sobre el `openapi.json` real de ambas aplicaciones:

**MS1** (`services/ms1_auth`):

```
securitySchemes: ['HTTPBearer']  ->  type: http, scheme: bearer
  POST /auth/register   security: (no declarado -> pública)
  POST /auth/login      security: (no declarado -> pública)
  GET  /auth/me         security: [{'HTTPBearer': []}]
```

**Gateway** (`gateway`):

```
securitySchemes: ['bearerAuth']  ->  type: http, scheme: bearer, bearerFormat: JWT
  POST /api/auth/login   security: []
  GET  /api/auth/me      security: [{'bearerAuth': []}]
  GET  /api/ordenes      security: [{'bearerAuth': []}]
```

### 3.2 Lectura de los resultados

- Los endpoints públicos (registro y login) **no** declaran `security`: el
  Swagger los muestra sin el botón de credenciales, que es lo correcto.
- Los protegidos sí la declaran, con el esquema correcto.
- `POST /api/auth/login` aparece como `security: []` (array vacío), que es
  explícitamente "público" en OpenAPI 3, a diferencia de "no declarado", que
  heredaría el `security` global.
- La Gateway **añade** `bearerFormat: JWT`, así que el Swagger muestra el tipo de
  token. MS1 no lo añade porque reutiliza el `HTTPBearer` de FastAPI.

### 3.3 Por qué esto importa en la práctica

El Swagger es lo que consume el equipo para integrar. Si `/api/ordenes` no
declarara el esquema, un integrator concluiría que el endpoint es público y su
cliente fallaría con `401` en desarrollo, sin ninguna pista de por qué. Declarar
el esquema convierte un error de integración en un error visible en el
documento.

---

## 4. Dependencias reutilizables de FastAPI

### 4.1 La separación que sostiene todo

Hay dos capas, y la frontera entre ellas es la decisión de diseño más
importante del sistema:

```
shared/auth.py            ->  PURE. Sin FastAPI, sin SQLAlchemy, sin BD.
  crear_token_acceso()        emite un JWT con el contrato oficial
  validar_token_acceso()      valida firma, exp y claims; devuelve PrincipalAutenticado
  NombreRol                   enum de los 3 roles oficiales
  PrincipalAutenticado        dataclass: usuario_id: int, roles: frozenset

 */dependencies.py        ->  ADAPTADOR FastAPI. Traduce HTTP a shared.auth.
  obtener_principal_actual()   Depends(_bearer) -> validar_token_acceso() -> 401
  requerir_roles(...)         guarda de rol insuficiente -> 403
```

`validar_token_acceso` **no consulta ninguna base de datos.** MS2 y MS3 pueden
autenticar a un usuario sin hablar con MS1, que es lo que permite que cada
microservicio tenga su propia base sin acoplamiento. El `usuario_id` que sale del
JWT es la **referencia lógica** entre servicios, sin clave foránea.

### 4.2 El patrón `auto_error=False` y por qué es obligatorio

Las cuatro dependencias usan:

```python
_bearer = HTTPBearer(auto_error=False)
```

Con el valor por defecto (`auto_error=True`), `HTTPBearer` responde **403** cuando
falta la cabecera `Authorization`. Eso está mal por dos razones:

1. **Semántica HTTP:** la ausencia de credenciales es "no autenticado" (`401`),
   no "autenticado pero sin permisos" (`403`).
2. **Consecuencia en el cliente:** un frontend que limpia la sesión al recibir
   un `401` **no** limpia la sesión al recibir un `403`. El usuario queda con una
   sesión muerta que reintenta en bucle.

Por eso el `401` se lanza explícitamente, siempre con la cabecera que indica el
esquema esperado:

```python
def _error_no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )
```

Y el mensaje es **idéntico** para token ausente, inválido y expirado. Distinguir
"expirado" de "firmado con otra clave" le diría a un atacante qué intentar.

### 4.3 Tres formas de aplicar la autorización

Las cuatro dependencias ofrecen las tres, y cada endpoint elige la que necesita:

```python
# 1. Solo proteger, sin saber quién llama (MS3)
@router.get("", dependencies=[Depends(requerir_roles(NombreRol.ADMINISTRADOR))])

# 2. Saber quién llama (MS1, MS2, MS3)
def endpoint(principal: PrincipalAutenticado = Depends(obtener_principal_actual)):
    ...

# 3. Encadenar: identidad + rol + recurso local (MS2)
def endpoint(cliente: Cliente = Depends(resolver_cliente_actual)):
    ...
```

`resolver_cliente_actual` es el caso más completo: encadena
`obtener_principal_actual` → exige rol `Cliente` → busca el perfil local, y
distingue los tres fallos con códigos distintos:

| Fallo | Código | Razón |
|---|---|---|
| Sin token o token inválido | `401` | No se sabe quién es |
| Rol insuficiente | `403` | Se sabe quién es, pero no le corresponde |
| Sin perfil `Cliente` en MS2 | `404` | La identidad es válida, el recurso no existe |

Ese `404` en lugar de `403` es deliberado y es la misma política de no
enumeración que aplica a las órdenes: no confirma si el perfil existe o no.

### 4.4 Cómo se prueban sin servidor ni base real

`tests/conftest.py` sustituye las bases por SQLite en memoria y sobrescribe la
dependencia de sesión con `app.dependency_overrides[get_db]`. El punto clave es
que **el código productivo no cambia**: los routers, la emisión del token, la
validación y la autorización son los mismos que corren en producción. Solo se
sustituyen la persistencia y, en el test de integración, el transporte HTTP.

Esto es lo que permite que 304 pruebas corran en segundos, sin Docker y sin
PostgreSQL.

---

## 5. El flujo de autorización completo

```
 Cliente (React / móvil)
        │  Authorization: Bearer <JWT>
        ▼
 Gateway (:8000)                    ← NO valida el token.
        │                           Solo enruta /api/* y reenvía la cabecera
        │                           intacta hacia el microservicio destino.
        ▼
 MS2 (:8002)
        │
        ├─ obtener_principal_actual()  ->  shared.auth.validar_token_acceso()
        │      sin token / inválido / expirado ......... 401
        │      válido -> PrincipalAutenticado(usuario_id, roles)
        │
        ├─ requerir_roles(...)  ¿el rol está entre los permitidos?
        │      no ...................................... 403
        │
        ├─ resolver_cliente_actual()  ¿existe el perfil local?
        │      no ...................................... 404
        │
        └─ el endpoint ejecuta la operación de negocio
```

**Por qué la Gateway no valida el token:** si lo hiciera, necesitaría el
secreto de firma de los cuatro servicios, y entonces podría firmar un token con
la identidad que quisiera. Al no validarlo, la Gateway queda estructuralmente
incapaz de falsificar una identidad: solo mueve bytes. La consecuencia
acostumbrada es que la Gateway no puede responder `401` por sí misma; siempre
delega ese juicio al microservicio, que es quien tiene el secreto.

---

## 6. Superficie de ataque revisada

| Riesgo | Estado | Evidencia |
|---|---|---|
| Secreto JWT con valor por defecto en el código | ✅ Ausente | `shared/auth.py::_validar_configuracion` exige ≥32 caracteres y lanza `ConfiguracionJWTError` si falta. `Settings.JWT_SECRET_KEY` es `SecretStr` sin default. `.env.example` solo trae placeholders. |
| Algoritmo negociable | ✅ No | Solo se admite `HS256`; el decode pasa `algorithms=["HS256"]` explícito, sin `none` |
| Token sin `exp` o sin `sub` | ✅ Rechazado | `options={"require_exp": True, "require_sub": True}` |
| `sub` no numérico (`"usr_1"`) | ✅ Rechazado | `_extraer_usuario_id` exige entero positivo |
| `roles` vacía, con duplicados o con rol desconocido | ✅ Rechazado | `_extraer_roles` valida los tres casos |
| Enumeración de usuarios en el login | ✅ Ausente | Mismo `401` y mismo mensaje para correo inexistente y contraseña incorrecta |
| Enumeración de recursos | ✅ Ausente | Recurso ajeno e inexistente devuelven el mismo `404` |
| CORS permisivo con credenciales | ✅ Ausente | Lista explícita + regex acotada a `https://*.vercel.app` |
| Token o contraseña en los logs del backend | ✅ Ausente | Único `logger.exception` del Gateway registra `url.path` y `request_id`; nunca cabeceras, body ni query string |
| Token en la consola del navegador | ✅ Corregido | `ErrorBoundary` ya no vuelca el objeto error (§7.5). Residual de React en desarrollo: §7.6 |
| Correo de usuario en la salida del seed | ✅ Corregido | `seed_usuarios_prueba.py` enmascara con `_ocultar_correo()` (§7.8) |
| `.env` real versionado | ✅ Ausente | Solo se versionan `.env.example` con placeholders |
| Contraseña del DSN en errores de conexión | ✅ Enmascarada | Comprobado: SQLAlchemy no incluye la contraseña en `str(error)` |
| `WWW-Authenticate` en el 401 de la Gateway | ⚠️ Se pierde | El proxy solo reenvía `content-type` (§7.7) |

---

## 7. Hallazgos y recomendaciones

La revisión de logs (tarea «Revisar que los logs no expongan contraseñas, tokens
ni datos sensibles») encontró **dos filtraciones reales**, que sí se corrigieron
porque son defectos y no refactors. Las secciones 7.5 a 7.8 son observaciones
que **no se tocaron**: son refactors o decisiones de mantenimiento.

### 7.1 `obtener_principal_actual` está copiado en los cuatro microservicios

La función es idéntica en MS1, MS2, MS3 y MS4 (y `_error_no_autenticado` también).
Hoy funciona porque `shared/auth.py` centraliza la parte difícil, pero las cuatro
copias tienen que actualizarse a la vez: si mañana se agrega un claim nuevo al
mensaje de error, hay que acordarse de los cuatro sitios.

*Recomendación:* mover el adaptador a `shared/dependencies.py`, parametrizado por
el secreto del servicio, y dejar en cada `*/dependencies.py` solo lo específico
(`resolver_cliente_actual` en MS2, la unidad de trabajo en MS3).

**No se hizo a propósito:** es un refactor sobre código cubierto por 304 pruebas
que hoy pasan, y su valor no compensa el riesgo en esta entrega. Queda como
tarea de mantenimiento.

### 7.2 `requerir_roles` sin argumentos se comporta distinto en MS1 y MS3

MS1 lanza `ValueError("Debe indicarse al menos un rol permitido")` si se invoca
sin roles; MS3 construye un `frozenset()` vacío y deniega todo con `403`. Ninguna
de las dos rutas es alcanzable desde los routers actuales, porque ambos pasan
siempre al menos un rol.

*Recomendación:* igualar MS3 a MS1, que falla ruidosamente en desarrollo en
lugar de denegar en silencio.

### 7.3 `shared/auth.py` no exporta explícitamente su API pública

Usa prefijo `_` para lo privado, pero no hay `__all__`. Funciona, y los
`from shared.auth import ...` son explícitos, así que es menor.

*Recomendación:* declarar `__all__` si se decide centralizar las dependencias del
punto 7.1.

### 7.4 CORREGIDO: MS4 tenía `obtener_principal_actual` sin usar

Este estudio se escribió antes de los endpoints de evidencias (Semana 5):
la nota original registraba que la dependencia estaba lista y ningún endpoint la
consumía todavía. Desde la Semana 5 todos los endpoints de `routers/evidencias.py`
la usan, junto con `obtener_token_bearer` (que reenvía el JWT a MS2 para validar
la orden). Ya no hay código muerto.

### 7.5 CORREGIDO: el `ErrorBoundary` volcaba el token de acceso en la consola

`frontend/src/presentation/components/ui/ErrorBoundary.tsx` tenía:

```ts
console.error('Error capturado por ErrorBoundary:', error, errorInfo);
```

Si el error capturado es un `AxiosError` —que es lo que ocurre cuando un fallo de
la API llega hasta el render— ese objeto lleva dentro
`config.headers.Authorization`. Al imprimirlo entero, la consola del navegador
muestra el **Bearer token en claro**. Y la consola es precisamente lo que queda
visible cuando se comparte pantalla en una sesión de soporte, o cuando se graba
la pantalla para un ticket.

*Corrección aplicada:* se registra solo `nombre`, `mensaje` y la pila de
componentes, que es lo que sirve para depurar, y nunca el objeto del error:

```ts
console.error(
  'Error capturado por ErrorBoundary:',
  `${error?.name ?? 'Error'}: ${error?.message ?? 'sin mensaje'}`,
  errorInfo.componentStack,
);
```

Añadida la prueba `no vuelca el token de acceso en la consola` en
`ErrorBoundary.test.tsx`. Se comprobó en las dos direcciones: **falla** contra el
código anterior y **pasa** contra el corregido. Para que la prueba sea real hay
que serializar el objeto recibido, porque `String(error)` solo devuelve el
mensaje y no delata el token que va anidado.

### 7.6 Residual conocido: React también registra el objeto error completo

Al verificar la corrección anterior apareció un segundo volcado que **no está en
nuestro código**: React, en desarrollo, registra por su cuenta el error que
captura con

```
console.error("%o\n\n%s\n\n%s\n", error, componentStack, mensaje)
```

y ahí el `error` vuelve a ser el `AxiosError` completo, con el token dentro.

*No se puede corregir desde la aplicación* sin dejar de capturar el error, así
que queda documentado. Consecuencias prácticas:

- No lanzar objetos `AxiosError` crudos durante el render; en su lugar, lanzar
  un error propio con un código y el mensaje.
- El impacto es de desarrollo, no de producción: los registros de React se
  elaboran en el build de desarrollo y el bundle de producción no los emite.
- Aun así, quien depure en desarrollo debe tratar la consola como un medio con
  datos sensibles: no pegar capturas de la consola en tickets sin censurar.

### 7.7 Observación: la Gateway no reenvía `WWW-Authenticate`

El proxy devuelve el cuerpo y el estado del microservicio, pero solo conserva la
cabecera `content-type` de la respuesta. Como MS1 responde los `401` con
`WWW-Authenticate: Bearer`, esa cabecera **se pierde** al pasar por la Gateway:

```
MS1 directo   : /auth/me  ->  401, WWW-Authenticate: Bearer
Por la Gateway: /api/auth/me -> 401, sin WWW-Authenticate
```

RFC 9110 pide que un `401` incluya `WWW-Authenticate`, para que el cliente sepa
qué esquema usar. Al cliente no le rompe nada (los navegadores con `fetch` ya
saben que el token va en `Authorization`), pero es una desviación del estándar.

*Recomendación:* en `gateway/routers/proxy.py`, reenviar también las cabeceras
de respuesta que no sean `hop-by-hop`. No se hizo en esta entrega porque cambia
el comportamiento del proxy y hay 19 pruebas de `test_gateway_rutas.py`
apoyándose en su contrato actual.

### 7.8 CORREGIDO: el seed imprimía los correos de los usuarios

`backend/scripts/seed_usuarios_prueba.py` imprimía la dirección completa de cada
cuenta creada (`Usuario creado: cliente@pruebas.cl`). Como la salida del script
termina en los logs del despliegue, era el único punto del backend donde salía
un dato de usuario a la salida estándar.

*Corrección aplicada:* los correos se enmascaran con `_ocultar_correo()`, que
conserva la inicial y el dominio (`c***@pruebas.cl`), que basta para saber qué
cuenta se sembró.

Residual aceptable y documentado a propósito: el propio archivo sigue
conteniendo las credenciales de prueba en su docstring, y
`CONEXIONES.md` las documenta. Son cuentas de la revisión, no datos reales; el
cambio evita que el patrón se arrastre a un seed de usuarios reales.
