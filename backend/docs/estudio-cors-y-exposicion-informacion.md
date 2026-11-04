# 🛡️ Estudio: Encabezados CORS y exposición de información en respuestas

**Ámbito:** Gateway (`gateway/`), contrato de errores (`gateway/errores.py`,
`gateway/esquemas.py`, `gateway/routers/proxy.py`), respuestas de error de los
microservicios (MS1–MS4) y despliegue en Vercel (`vercel.json`).

**Estado:** estudio sobre el código en ejecución. No introduce cambios de
comportamiento: la revisión no encontró defectos que requieran corrección de
código; los hallazgos de la sección 5 quedan como observaciones/recomendaciones
pendientes de decisión del equipo.

Complementa `estudio-seguridad-transporte.md` (§2 ya analiza la configuración
CORS desde la óptica del transporte); este documento la profundiza y añade el
eje de **exposición de información en los cuerpos y cabeceras de respuesta**.

---

## 1. Por qué este estudio

Las respuestas HTTP son la superficie visible del backend. Dos familias de
decisiones la definen:

1. **Encabezados CORS**: qué orígenes y cabeceras el navegador permite cruzar
   hacia la API. Mal configurado, abre el backend a sitios ajenos.
2. **Exposición de información**: qué revelan los cuerpos de error, las
   cabeceras reenviadas y los endpoints de documentación. Fugas típicas de
   OWASP: stack traces, SQL, URLs internas, nombres de microservicios,
   versiones de software (`Server`), listas de validación.

Se revisan juntos porque el proxy de la Gateway es el que decide qué cabeceras
del microservicio llegan al cliente: un error CORS y una fuga de información
viven en los mismos flujos.

---

## 2. CORS: revisión de la configuración vigente

### 2.1 Configuración (`gateway/main.py` + `gateway/config.py`)

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

| Parámetro | Valor por defecto | Evaluación |
|---|---|---|
| `allow_origins` | `["http://localhost:5173", "http://localhost:8000"]` | ✅ Lista explícita, sin `*`. Es la condición que exige `allow_credentials=True`. |
| `allow_origin_regex` | `https://[a-z0-9-]+\.vercel\.app` | ⚠️ Ver hallazgo H2 (§5.2): acotada por charset, no por dominio del proyecto. |
| `allow_credentials` | `True` | ✅ Cliente envía `Bearer` en `Authorization`, no cookies; aun así la cabecera sigue el patrón estándar del proyecto. |
| `allow_methods` | `*` | ✅ Aceptable: el navegador solo ecoa los métodos realmente solicitados; la autorización real es el `401/403` del microservicio. |
| `allow_headers` | `*` | ✅ Aceptable: en el *preflight* Starlette hace eco de las `Access-Control-Request-Headers` solicitadas; no concede nada extra. |
| `expose_headers` | `["X-Request-ID"]` | ✅ Operabilidad: el frontend puede correlacionar un error con los logs. |

### 2.2 El orden de middlewares y el `500` con CORS

`gateway/main.py` monta, de afuera hacia adentro: `RequestIdMiddleware` →
`CORSMiddleware` → `ManejoErroresMiddleware`. El manejador de `500` vive *por
dentro* de CORS deliberadamente (`gateway/errores.py`, docstring): si el error
no controlado se resolviera por fuera, la respuesta saldría sin
`Access-Control-Allow-Origin` y el navegador la reportaría como error de red
opaco en lugar de un `500` legible. **Cumple**, y está cubierto por
`tests/test_gateway_formato.py` (el `500` generado por la Gateway conserva el
`ACAO` de la prueba de origen permitido).

### 2.3 Cabeceras de respuesta del microservicio (proxy)

`gateway/routers/proxy.py` filtra lo que llega al cliente:

- **Hop-by-hop** (`connection`, `transfer-encoding`, `keep-alive`, `te`,
  `trailers`, `upgrade`, `proxy-*`, `host`, `content-length`): correcto, no
  pertenecen al cliente.
- **`server` y `date`**: se excluyen las del microservicio y las reconstruye
  Starlette para la Gateway — impide que la respuesta pública filtre la
  infraestructura interna (no el `Server: uvicorn` de la Gateway misma, H5).
- **`x-request-id`**: se excluye la del upstream; la impone la Gateway con el
  valor del `RequestIdMiddleware`, y el cliente no puede inyectar cabeceras
  arbitrarias porque el middleware valida el formato con la regex
  `^[A-Za-z0-9-]{1,128}$` (`gateway/middleware.py`) antes de ecoar el suyo.
- **`content-encoding`**: se excluye porque el body ya viene descomprimido por
  HTTPX; reenviar la cabecera rompería la decodificación del cliente.
- **`access-control-*`**: se excluyen para que el microservicio (que no tiene
  CORS propio) nunca duplique las cabeceras que ya coloca la Gateway.
- **`Location`** (`routers/proxy.py::_reescribir_location`): las URLs
  internas del microservicio (redirecciones 307, `Location` de 201) se
  reescriben a la URL pública `/api/...`: una URL interna
  (`http://ms-taller/...`) **nunca sale al cliente**. Cubierto por
  `tests/test_gateway_errores_proxy.py::test_...location...`.

### 2.4 Cabeceras de petición reenviadas

El proxy reenvía las cabeceras del cliente excepto las prohibidas, y añade
`X-Forwarded-For/Proto/Host`. No hay eco de cabeceras arbitrarias del
atacante hacia la respuesta (no hay *header reflection*). El `X-Forwarded-*`
revela el origen real para logs y un eventual rate limit; no sale al
cliente en ninguna respuesta.

### 2.5 Cobertura de pruebas existente (CORS)

| Prueba | Qué garantiza |
|---|---|
| `tests/test_autenticacion_canales.py` (§ Plataforma web) | Preflight 200 sin llegar a MS1; `Authorization` permitido; `ACAO` eco del origen exacto (no `*`) con credentials; origen ajeno sin `preflight` (400) y sin `ACAO` en la respuesta real. |
| `tests/test_autenticacion_canales.py` (§ Aplicación móvil) | Sin `Origin` funciona igual y sin `ACAO`. |
| `tests/test_gateway_estructura.py` | Origen permitido ecoa; origen ajeno no. |
| `tests/test_gateway_errores_proxy.py` | `server` no sale; `x-request-id` es el de la Gateway; `X-Forwarded-*` se arman en el proxy; `Location` se reescribe. |
| `tests/test_gateway_formato.py` | El `500` interno de la Gateway conserva `ACAO` y formato común. |

---

## 3. Exposición de información en los cuerpos de respuesta

### 3.1 El formato común de error de la Gateway

`gateway/errores.py` + `gateway/esquemas.py` definen un único cuerpo de error
propio de la Gateway:

- **Ninguna rama del catálogo filtra detalles internos.** Los mensajes están
  redactados para el usuario: `MICROSERVICIO_INALCANZABLE`, `TIEMPO_AGOTADO`,
  `GATEWAY_SATURADA`, `ERROR_MICROSERVICIO`, `ERROR_INTERNO`,
  `CUERPO_DEMASIADO_GRANDE` (mensaje genérico, sin el límite exacto), etc.
- El bloque `error` solo lleva `codigo`, `estado`, `ruta` y `request_id`:
  datos de trazabilidad, no internos.
- Los errores **JSON** del microservicio pasan intactos (decisión 3 del
  catálogo), ya que están diseñados por cada servicio para el cliente; los
  **no JSON** (incluido el `500` "Internal Server Error" plano de un
  microservicio sin manejador) se normalizan a `ERROR_MICROSERVICIO`
  genérico: el detalle técnico interno no llega al cliente.
- El único `logger.exception` de la Gateway registra `url.path` y
  `request_id`: nunca body, cabeceras ni query string (verificado en el
  estudio de transporte §6).

### 3.2 Los `detail=str(exc)` de los routers

Los `detail=str(exc)` encontrados en `routers/` (MS1 `auth.py`, MS2
`ordenes.py`/`vehiculos.py`) levantan **excepciones de negocio propias**, cuyos
mensajes están redactados como texto final para el cliente (por ejemplo
`"Correo o contraseña incorrectos"`, `"La orden no se encuentra"`). No hay
ningún caso donde `str(exc)` pueda revelar una excepción técnica (SQL,
conexión): esas se traducen a errores controlados antes o responden 500
genérico. **Cumple.**

### 3.3 Errores 500 de los microservicios

- **MS4** tiene manejador `Exception` propio (`services/ms4_evidencias/main.py`,
  `checklist 5.5`): 500 genérico, nunca mensaje de excepción, traceback,
  bucket, clave de objeto ni endpoint del almacenamiento. El traceback solo
  queda en nivel DEBUG (`services/registro.py`). **Cumple.**
- **MS3** traduce errores de persistencia a 404/409/422/500 con mensajes
  diseñados; su docstring lo garantiza: *"Nunca devuelve SQL ni parámetros"*.
- **MS1 y MS2** no tienen manejador `Exception`: un error no controlado
  responde el "Internal Server Error" plano *por defecto de FastAPI*, que no
  incluye stack ni mensaje. No es fuga, pero la respuesta no es JSON ni lleva
  el formato común; si llega por la Gateway, el proxy la normaliza a
  `ERROR_MICROSERVICIO` (§3.1). **Cumple vía Gateway; observación menor vía
  acceso directo** (H3).

### 3.4 Documentación OpenAPI/Swagger expuesta

| App | `/docs` | `/openapi.json` | Nota |
|---|---|---|---|
| Gateway | Sí (`/docs` con esquema reescrito) | Sí | Se expone por diseño: es la documentación pública de la API. |
| MS3 | Sí (`/docs`, `/redoc` relativos) | Sí | **Intencional** (`main.py`, comentarios: Swagger bajo `/ms3` en Vercel requiere URL relativa al `openapi.json`). |
| MS1, MS2, MS4 | Sí (por defecto de FastAPI) | Sí | Por defecto; nadie las desactivó. |

Este es el hallazgo **H1** (§5.1): en producción (Vercel reescribe `/ms1/…` a
cada servicio, `vercel.json`) la documentación interna de cada microservicio
queda pública sin necesidad de credenciales.

### 3.5 Cabeceras `Server` / versiones

- El proxy descarta la cabecera `server` del microservicio, así que la
  respuesta pública nunca combina dos cabeceras; queda la `Server: uvicorn`
  que genera la propia Gateway/ASGI.
- `health`/`health/db` devuelven solo `status` y `SERVICE_NAME` (lógico):
  sin DSN, versión del motor, ni puertos internos. **Cumple.**
- `indice()` de la Gateway expone nombres de microservicios ("ms1_auth", ...) y
  prefijos `/api/*` que enruta: es información pública por diseño (sirve de
  índice del backend); no expone URLs internas. Las menciones del
  `health_servicios` (`latencia_ms`, `codigo_http`) también están ajustadas.
  **Cumple.**

---

## 4. Checklist de sobreexposición típica (OWASP)

| Caso | Situación OBSERVADA |
|---|---|
| Stack trace en el body de un `500` | ✅ Ausente (MS4 genérico; servicios pasan normalizados por la Gateway). |
| Mensaje de excepción técnica (`str(exc)`) de origen técnico en el body | ✅ Ausente: todos los `detail=str(exc)` son excepciones de negocio con mensaje para cliente. |
| SQL, DSN o credenciales en un error | ✅ Ausente (estudio de transporte §6 ya lo verificó). |
| URL interna de red interna en la respuesta (`Location`, health, logs) | ✅ Ausente: `_reescribir_location` + `health_servicios` solo con estados. |
| Cabeceras de respuesta del microservicio no aplicables (hop-by-hop, `server`, CORS duplicado, `content-encoding`) | ✅ Filtradas por `_CABECERAS_RESPUESTA_EXCLUIDAS`. |
| Eco de cabeceras/petición del atacante (header injection/reflection) | ✅ Ausente: el proxy nunca ecoa cabeceras del cliente a la respuesta; `X-Request-ID` se valida con regex. |
| CORS comodín (`*`) con credenciales | ✅ Ausente: origen explícito + regex anclada a `https://`. |
| Documentación interna pública sin credenciales | ⚠️ Presente en producción (H1). |
| Regex de orígenes amplia en subdominio de terceros | ⚠️ Presente en producción (H2). |

---

## 5. Hallazgos

### 5.1 H1 — Swagger y `openapi.json` de los microservicios, públicos en producción

**Qué ocurre:** `vercel.json` reescribe `/ms1/…`, `/ms2/…`, `/ms3/…`, `/ms4/…`
directamente a cada microservicio sin pasar por la Gateway. Los cuatro exponen
`/docs`, `/redoc` y `/openapi.json` sin autenticación. En MS3 es deliberado
(comentario en `main.py`: la documentación bajo `/ms3` necesita URL relativa
para funcionar); en MS1, MS2 y MS4 es simplemente el valor por defecto de
FastAPI.

**Riesgo:** bajo — la documentación solo confirma lo que un observador ya
puede descubrir por sondeo contra la API (el `401/403` es la barrera real), y
la documentación no revela secretos ni datos. Pero es superficie de
reconocimiento gratuita: enumera todos los endpoints, sus parámetros y
mensajes 422.

**Evaluación: observación, no defecto corregido.** Para cerrarlo habría que
decidir con el equipo: (a) condicionar con `MS*_DOCS_ENABLED=false` en
producción; (b) exigir credenciales sobre `/docs/*`; o (c) aceptarlo como
decisión de transparencia académica. Cambiarlo de una vez puede romper la
revisión y la práctica actual del equipo (el estudio de transporte ya
documenta esa disposición), así que solo se registra.

### 5.2 H2 — La regex CORS admite subdominios de `vercel.app` de terceros

**Qué ocurre:** `https://[a-z0-9-]+\.vercel\.app` coincide con **cualquier**
subdominio de `vercel.app`, incluidos los desplegados por terceros
(`proyecto-ajeno.vercel.app`). El estudio de transporte (§2.3) la describe como
"acotada"; lo es por charset (`https://`, grupos `[a-z0-9-]`, sin subdominios
profundos), pero no por **dominio del proyecto**: cualquiera puede crear un
despliegue Vercel que case con la regex.

**Riesgo real hoy: nulo.** La autenticación es `Bearer` en `Authorization`
(no hay cookies de sesión ambientales), así que un origen ajeno que case con la
regex solo puede hacer peticiones con un token que le entregue expresamente el
usuario — no gana nada. Pero si mañana se añade autenticación por cookie, esa
regex se convertiría en un agujero CSRF-CORS real con `allow_credentials=True`.

**Evaluación: observación, no defecto corregido.** Opciones si el
equipo decide cerrarlo: (a) acotar la regex a los nombres de despliegue reales
del equipo (lista de `allow_origins` por ambiente); (b) fijar
`GATEWAY_CORS_ALLOW_CREDENTIALS=false` mientras no haya cookies. No se toca en
esta tarea: cambiar el CORS de producción sin coordenadas de despliegue
confirmadas puede romper los previews del equipo.

### 5.3 H3 — El `500` no controlado de MS1/MS2 carece de formato común

**Qué ocurre:** MS4 sí tiene manejador `Exception` (500 genérico propio);
MS3 lo traduce por tipos; MS1 y MS2 no. Por la Gateway la diferencia es
invisible (se normaliza a `ERROR_MICROSERVICIO`), pero accediendo directo al
microservicio (producción en `/ms1/…`) la respuesta es `"Internal Server Error"`
texto plano sin JSON ni trazabilidad.

**Evaluación: observación de robustez, no de fuga.** No hay exposición de
información. Si se decide unificar, es un refactor de los cuatro `main.py`
(análogo al de MS4), fuera del alcance "revisar" de esta tarea.

### 5.4 H4 — `indice()` y `health_servicios` revelan la topología lógica

Nombres de microservicios, prefijos enrutados y latencias por servicio están en
las respuestas públicas. **Aceptado por diseño** (documentación operativa del
backend); no expone URLs, credenciales ni detalles técnicos. Registrado para
que la decisión quede explícita; no se propone cambio.

### 5.5 H5 — `Server: uvicorn` en cada respuesta

La cabecera `Server` del ASGI queda en todas las respuestas del backend. Es una
revelación menor del stack (un observador confirma "Python/uvicorn"). OWASP la
lista solo como *reducción de ruido*: dado que la tecnología ya es evidente
por el formato de errores 422 de FastAPI, quitarla implica configuración del
ASGI o un middleware, con ganancia marginal. **No se toca.**

---

## 6. Correcciones que NO se aplicaron (y por qué)

- **H1** (documentación): requiere decisión de despliegue; MS3 la necesita por
  diseño Vercel y MS1/MS2/MS4 pueden depender de ella en la práctica del equipo.
- **H2** (regex CORS): tocar el CORS de producción sin confirmar los dominios
  reales de despliegue puede bloquear a los integradores legítimos.
- **H3** (manejador `Exception` en MS1/MS2): refactor de los cuatro `main.py`;
  hoy el error ya sale normalizado por la Gateway.
- **H5** (`Server`): ganancia marginal, prepararía un cambio de ASGI.

---

## 7. Conclusión

El perímetro de cabeceras y cuerpos de respuesta está **bien diseñado**:

- CORS con origen explícito + regex `https://`, credenciales coherentes con la
  ausencia de cookies, y middlewares ordenados para que hasta el `500` salga
  con el `ACAO` correcto.
- El proxy filtra cabeceras upstream, desactiva el eco de cabeceras del
  atacante, valida el `X-Request-ID` y reescribe cada `Location` interno: no
  hay vía de fuga por cabeceras conocida.
- Los cuerpos de error usan mensajes pensados para el cliente; los `500` son
  genéricos y los traceback solo quedan en logs de servidor.

Los cinco hallazgos son observaciones de decisión de equipo o de mejora
progresiva, no defectos corregibles de manera mínima y segura dentro del alcance
"revisar". El plan recomendado, en orden, es: acotar/agregar credenciales CORS
(H2), decidir la visibilidad de la documentación por servicio (H1), unificar el
manejador `500` de MS1/MS2 (H3) y, por último, el ruido de `Server` (H5).
