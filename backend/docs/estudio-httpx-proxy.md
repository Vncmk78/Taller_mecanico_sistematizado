# Estudio: HTTPX, timeouts y patrones de proxy con FastAPI

Semana 4 · Bastián Liempi · Taller de Integración II (Grupo 10)

La Gateway del SGTM es un **proxy inverso**: recibe `/api/*`, elige el
microservicio por el primer segmento (`gateway/rutas.py`) y reenvía la petición
con **HTTPX** (`gateway/routers/proxy.py`). Este estudio revisa cómo funciona
HTTPX, qué pasa hoy en el proxy y fija las decisiones que aplican las tareas
siguientes de la Semana 4: *Estandarizar mapeo de errores*, *Agregar health
checks* y *Pruebas de integración de los cuatro prefijos*.

Versiones del proyecto: `httpx 0.28`, `fastapi 0.14x`, `uvicorn[standard]`.

---

## 1. Qué es HTTPX y por qué lo usa la Gateway

HTTPX es un cliente HTTP para Python con la misma API en modo síncrono
(`httpx.Client`) y asíncrono (`httpx.AsyncClient`). La Gateway es una app
FastAPI asíncrona: mientras espera la respuesta de un microservicio, el event
loop sigue atendiendo otras peticiones. Por eso usa **`AsyncClient`**; un
cliente síncrono (o `requests`) bloquearía el loop y la Gateway atendería de a
una petición.

| Pieza | Para qué sirve |
|---|---|
| `AsyncClient` | Mantiene un **pool de conexiones** (keep-alive) hacia los servidores. |
| `httpx.Timeout` | Límites de tiempo por fase de la petición (ver §3). |
| `httpx.Limits` | Tamaño del pool: `max_connections` (100 por defecto), `max_keepalive_connections` (20), `keepalive_expiry` (5 s). |
| `AsyncHTTPTransport(retries=n)` | Reintenta **solo** fallos al conectar (nunca una petición ya enviada). |
| `client.send(request, stream=True)` | Recibe la respuesta por partes, sin cargarla entera en memoria. |

Por defecto HTTPX **no sigue redirecciones** (`follow_redirects=False`), lo que
es correcto en un proxy: la redirección debe llegar al cliente tal cual.

---

## 2. Cómo está hoy el proxy (`gateway/routers/proxy.py`)

```python
cuerpo = await request.body()                       # body completo en memoria
async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as cliente:
    respuesta = await cliente.request(...)          # un cliente NUEVO por petición
except httpx.HTTPError:
    return respuesta_error(..., estado=502, ...)    # todo error -> 502
return Response(respuesta.content, respuesta.status_code,
                headers={"content-type": ...})      # solo reenvía Content-Type
```

Funciona y está probado (17/17 en `docs/pruebas-comunicacion-gateway.md`), pero
tiene cinco puntos a mejorar:

| # | Hallazgo | Consecuencia |
|---|---|---|
| H1 | Se crea y destruye un `AsyncClient` **por petición**. | No se reutilizan conexiones: cada petición paga de nuevo el TCP (y TLS en producción). Más latencia. |
| H2 | Un solo timeout de **30 s** para todo. | Si un microservicio está caído en otra máquina, la Gateway puede esperar hasta 30 s solo para conectar. |
| H3 | **Todo** `httpx.HTTPError` responde `502`. | No se distingue "no pude conectar" de "conecté pero tardó demasiado". `config.py` ya anuncia un `504` que nunca se envía. |
| H4 | De la respuesta solo se reenvía `Content-Type`. | Se pierden cabeceras que el frontend necesita: `WWW-Authenticate` (401 de MS2), `Location`, `Content-Disposition` (descargas), `Cache-Control`, `Retry-After`. |
| H5 | `await request.body()` lee el body completo. | Con fotos es aceptable; con videos consume memoria (checklist 4.3). |

---

## 3. Timeouts: las cuatro fases

`httpx.Timeout` separa el tiempo en fases. Cada una lanza su propia excepción:

| Fase | Qué mide | Excepción | Qué significa para la Gateway |
|---|---|---|---|
| `connect` | Establecer la conexión TCP (y TLS). | `ConnectTimeout` | El servicio no contesta: probablemente caído o red cortada. |
| `read` | Espera **entre** bloques de la respuesta (no el total). | `ReadTimeout` | El servicio recibió la petición pero no respondió a tiempo. |
| `write` | Espera entre bloques al **enviar** el body. | `WriteTimeout` | La subida no avanza (típico con archivos grandes). |
| `pool` | Esperar una conexión libre del pool. | `PoolTimeout` | La Gateway está saturada (pool lleno). |

Ejemplo: `httpx.Timeout(10.0, connect=3.0)` → 3 s para conectar y 10 s para
las demás fases. El timeout se puede **sobreescribir por petición**
(`cliente.request(..., timeout=...)`), útil para la subida de evidencias.

> **Decisión 1 — Timeouts por fase.** `connect=3 s`, `read=15 s`,
> `write=15 s`, `pool=5 s`, configurables por entorno (`GATEWAY_TIMEOUT_*`).
> El prefijo `evidencias` usa `read`/`write` más largos (60 s) porque sube
> archivos. Conectar debe ser rápido: si en 3 s no hay conexión, el servicio
> no está.

---

## 4. Jerarquía de excepciones y mapeo a respuestas de la Gateway

```
httpx.HTTPError
├── httpx.RequestError            (no hubo respuesta)
│   ├── TransportError
│   │   ├── TimeoutException
│   │   │   ├── ConnectTimeout
│   │   │   ├── ReadTimeout
│   │   │   ├── WriteTimeout
│   │   │   └── PoolTimeout
│   │   ├── NetworkError  (ConnectError, ReadError, WriteError, CloseError)
│   │   ├── ProtocolError (RemoteProtocolError, LocalProtocolError)
│   │   └── ProxyError, UnsupportedProtocol
│   ├── DecodingError
│   └── TooManyRedirects
└── httpx.HTTPStatusError        (solo con raise_for_status(); el proxy no lo usa)
```

Clave para un proxy: **un 4xx/5xx del microservicio NO es una excepción**. Es
una respuesta válida que se reenvía. Solo cuando no hay respuesta la Gateway
genera su propio error.

> **Decisión 2 — Mapeo de fallos de red** (para *Estandarizar mapeo de
> errores*):
>
> | Excepción | Estado | Código del catálogo | Mensaje al cliente |
> |---|---|---|---|
> | `ConnectError`, `ConnectTimeout` | 502 | `MICROSERVICIO_INALCANZABLE` | "El servicio no está disponible. Intente más tarde." |
> | `ReadTimeout`, `WriteTimeout` | 504 | `TIEMPO_AGOTADO` (nuevo) | "El servicio tardó demasiado en responder." |
> | `PoolTimeout` | 503 | `GATEWAY_SATURADA` (nuevo) | "La Gateway está ocupada. Intente más tarde." |
> | Otro `RequestError` | 502 | `MICROSERVICIO_INALCANZABLE` | Igual que arriba. |
>
> El mensaje nunca incluye la URL interna ni el texto de la excepción (se
> registran en el log con el `request_id`).

> **Decisión 3 — Respuestas de error de los microservicios.** Un 4xx/5xx que
> llega del microservicio se reenvía con su estado y su body (`{"detail": ...}`
> de FastAPI), **sin reescribirlo**: el frontend ya lee `detail`. Solo se
> normaliza el caso en que el body no es JSON (por ejemplo, un 500 en texto
> plano o HTML de un proxy intermedio): se reemplaza por el formato común con
> código `ERROR_MICROSERVICIO` y el mismo estado.

---

## 5. Cliente compartido: ciclo de vida

Crear el cliente por petición (H1) desperdicia el pool. Hay dos patrones:

| Patrón | Cómo | Pro | Contra |
|---|---|---|---|
| **Lifespan** | `@asynccontextmanager` en `FastAPI(lifespan=...)` crea el cliente al arrancar y lo cierra al apagar; se guarda en `app.state`. | Es el patrón recomendado por FastAPI. | En tests, el lifespan solo corre dentro de `with TestClient(app):`. Además, en funciones serverless (Vercel) el ciclo de vida no está garantizado. |
| **Perezoso (lazy)** | Una función `obtener_cliente()` crea el cliente la primera vez y lo reutiliza; el lifespan solo lo **cierra**. | Funciona igual en local, en tests y en serverless. | Un poco más de código. |

> **Decisión 4 — Un `AsyncClient` compartido creado de forma perezosa**
> (`gateway/cliente_http.py`), con los timeouts de la Decisión 1,
> `Limits(max_connections=100, max_keepalive_connections=20)` y
> `AsyncHTTPTransport(retries=1)`. El lifespan de la app lo cierra al
> apagar. Los tests con respx siguen funcionando: respx intercepta cualquier
> cliente HTTPX.

---

## 6. Reintentos

`AsyncHTTPTransport(retries=n)` reintenta **solo** `ConnectError` y
`ConnectTimeout`: la petición todavía no salió, así que reintentar es seguro
incluso para un `POST`. Reintentar después de un `ReadTimeout` **no** es seguro
para `POST`/`PATCH`: el microservicio pudo haber creado el recurso y el
reintento lo duplicaría (dos órdenes, dos evidencias).

> **Decisión 5 — Un solo reintento, solo al conectar.** Nada de reintentos
> por timeout de lectura ni por respuestas 5xx en la Gateway.

---

## 7. Cabeceras

**Hacia el microservicio.** Ya se quitan las cabeceras *hop-by-hop*
(`connection`, `keep-alive`, `transfer-encoding`, `te`, `upgrade`, …), `host`
y `content-length` (HTTPX las recalcula). Se agrega `X-Request-ID`. Falta
informar el origen real de la petición:

- `X-Forwarded-For` (IP del cliente), `X-Forwarded-Proto` y `X-Forwarded-Host`.
  Sirven para logs y, más adelante, para el límite de frecuencia (checklist 4.4).

**Hacia el cliente (H4).** En vez de reenviar solo `Content-Type`, reenviar
todas las cabeceras de la respuesta **excepto** las hop-by-hop y las que
cambian al reconstruir la respuesta:

- `content-length`: la recalcula Starlette.
- `content-encoding`: `respuesta.content` ya viene **descomprimido** por HTTPX;
  reenviar `gzip` haría que el navegador intente descomprimir texto plano.

> **Decisión 6 — Cabeceras.** Hacia el microservicio: quitar hop-by-hop,
> agregar `X-Request-ID` y `X-Forwarded-*`. Hacia el cliente: reenviar todo
> salvo hop-by-hop, `content-length` y `content-encoding`. Así llegan
> `WWW-Authenticate`, `Location`, `Content-Disposition`, `Cache-Control` y
> `Retry-After`.

---

## 8. Streaming (bodies grandes)

Para no cargar archivos enteros en memoria (H5), HTTPX y Starlette permiten
pasar el body por partes:

```python
peticion = cliente.build_request(metodo, url, headers=h, content=request.stream())
respuesta = await cliente.send(peticion, stream=True)
return StreamingResponse(respuesta.aiter_raw(), status_code=respuesta.status_code,
                         headers=h_resp, background=BackgroundTask(respuesta.aclose))
```

Es el patrón correcto para subir y bajar videos, pero tiene costos: la
respuesta ya no se puede inspeccionar (no se podría aplicar la Decisión 3) y
en Vercel las funciones tienen además un **límite de tamaño de body por
petición** (del orden de pocos MB; verificar el valor vigente en la
documentación de Vercel), así que un video nunca pasaría por la Gateway en
producción de todos modos.

> **Decisión 7 — Sin streaming en la Semana 4.** Fotos y JSON siguen con
> body en memoria. Los videos usan el flujo C del estudio de almacenamiento
> (POST prefirmado directo a MinIO/S3), que evita pasar el archivo por la
> Gateway. El límite de tamaño con `413` en la Gateway queda para la
> Semana 5 (checklist 4.2).

---

## 9. Health checks agregados

Para *Agregar endpoints de health check*: la Gateway puede consultar el
`/health` de los cuatro microservicios **en paralelo** con `asyncio.gather` y
el cliente compartido, con un timeout corto (2 s) para que un servicio caído
no bloquee la respuesta.

> **Decisión 8 — `GET /api/health/servicios`.** Responde 200 si todos están
> arriba y 503 si alguno falla, con el detalle por servicio
> (`{"ms1": "ok", "ms3": "caido", ...}`) y la latencia de cada uno. No expone
> URLs internas. `/api/health` sigue respondiendo solo por la Gateway (lo usa
> Vercel y no debe depender de los demás).

---

## 10. Cómo probarlo

Los tests de la Gateway ya usan **respx**, que permite simular cada fallo:

```python
api_mock.get("http://ms2/vehiculos").mock(side_effect=httpx.ConnectError("x"))   # -> 502
api_mock.get("http://ms2/vehiculos").mock(side_effect=httpx.ReadTimeout("x"))    # -> 504
api_mock.get("http://ms2/vehiculos").mock(side_effect=httpx.PoolTimeout("x"))    # -> 503
api_mock.get("http://ms2/vehiculos").mock(
    return_value=httpx.Response(401, headers={"WWW-Authenticate": "Bearer"}))    # cabecera llega
```

Y la prueba real con servicios levantados: `scripts/prueba_comunicacion.py`.

---

## 11. Resumen de decisiones

| # | Decisión | Se aplica en |
|---|---|---|
| 1 | Timeouts por fase: 3 / 15 / 15 / 5 s; 60 s para `evidencias`. | Estandarizar mapeo de errores |
| 2 | `ConnectError` → 502, `Read/WriteTimeout` → 504, `PoolTimeout` → 503. | Estandarizar mapeo de errores |
| 3 | Errores 4xx/5xx del microservicio pasan tal cual; se normaliza solo el body no-JSON. | Estandarizar mapeo de errores |
| 4 | Un `AsyncClient` compartido, perezoso, cerrado en el lifespan. | Estandarizar mapeo de errores |
| 5 | Un reintento, solo al conectar. | Estandarizar mapeo de errores |
| 6 | Reenviar cabeceras de respuesta (salvo hop-by-hop, `content-length`, `content-encoding`) y agregar `X-Forwarded-*`. | Estandarizar mapeo de errores |
| 7 | Sin streaming por ahora; videos por POST prefirmado. | Semana 5 (subida) |
| 8 | `GET /api/health/servicios` en paralelo, 200/503. | Agregar health checks |

## Referencias

- HTTPX — *Timeouts*, *Resource Limits*, *Exceptions*, *Transports* y *Async
  Support* (documentación oficial, `www.python-httpx.org`).
- FastAPI — *Lifespan Events* y *Advanced: Custom Response / StreamingResponse*.
- Starlette — `Request.stream()`, `StreamingResponse`, `BackgroundTask`.
- RFC 9110 (HTTP Semantics) §7.6.1 — cabeceras de conexión (*hop-by-hop*).
- `docs/estudio-almacenamiento-objetos.md` (flujo C) y
  `docs/checklist-seguridad-evidencias.md` (4.2 a 4.5).
