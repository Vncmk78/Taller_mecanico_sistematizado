# Estudio: resiliencia básica, timeouts y retries entre servicios

Semana 7 · Bastián Liempi · Taller de Integración II (Grupo 10)

El SGTM ya no es una sola app: una petición del frontend pasa por la Gateway y
puede encadenar llamadas entre microservicios (MS3 → MS2 → MS3, MS4 → MS2 y
MS3). Cuando una pieza se cae o se pone lenta, el resto tiene que fallar
**rápido, de forma predecible y sin duplicar operaciones**. Este estudio revisa
cómo está hoy el sistema, qué patrones de resiliencia aplican a nuestro tamaño y
fija las decisiones que implementan las tareas siguientes de la Semana 7:
*Configurar timeouts por servicio y respuestas estandarizadas* e *Implementar
comprobación de disponibilidad de servicios para diagnóstico*.

Parte de lo ya decidido en `estudio-httpx-proxy.md` (Semana 4: timeouts por
fase, mapeo 502/503/504, un reintento al conectar) y lo extiende a las llamadas
**entre** servicios.

---

## 1. Conceptos

| Concepto | Qué significa | Riesgo si falta |
|---|---|---|
| **Timeout** | Tiempo máximo que se espera a otro servicio antes de rendirse. | Una petición colgada retiene una conexión y un worker indefinidamente; con suficientes, la Gateway se satura (fallo en cascada). |
| **Presupuesto de tiempo** (*timeout budget*) | El timeout de quien llama debe cubrir la suma de lo que el llamado puede esperar aguas abajo. | Si la Gateway corta antes que MS3, el cliente ve `504` aunque MS3 termine bien la operación (se guardó, pero el usuario cree que falló). |
| **Retry** | Repetir automáticamente una petición fallida. | Duplicar escrituras (`POST` repetido = dos órdenes) y multiplicar la carga justo cuando el servicio está mal (*retry storm*). |
| **Idempotencia** | Repetir la operación produce el mismo resultado que hacerla una vez. | Sin ella no hay retry seguro de escrituras. |
| **Backoff con jitter** | Esperar cada vez más entre reintentos, con una parte aleatoria. | Sin jitter, todos los clientes reintentan sincronizados y golpean juntos. |
| **Circuit breaker** | Tras N fallos seguidos, dejar de llamar al servicio un tiempo y fallar de inmediato. | Sin él, cada petición paga el timeout completo contra un servicio que se sabe caído. |
| **Health check** | Endpoint barato que dice si el servicio (y sus dependencias) responde. | Diagnosticar un incidente a ciegas: no se sabe si cayó el proceso, la base o el almacenamiento. |
| **Degradación controlada** | Responder algo útil (o un error claro y reintentable) cuando una dependencia falla. | Errores genéricos `500` que no dicen si conviene reintentar. |

Regla práctica de la industria (AWS Builders' Library, Google SRE): **reintentar
en una sola capa**, siempre con límite y backoff, y **solo** operaciones
idempotentes o que la petición nunca llegó a enviar.

---

## 2. Cómo está hoy el sistema

### 2.1 Gateway → microservicios (`gateway/cliente_http.py`)

- Un `httpx.AsyncClient` compartido con timeouts por fase: conectar 3 s,
  leer/escribir 15 s, pool 5 s; el prefijo `evidencias` usa 60 s de
  lectura/escritura.
- `AsyncHTTPTransport(retries=1)`: **un** reintento, solo ante
  `ConnectError`/`ConnectTimeout` (la petición no salió; seguro incluso para
  `POST`).
- Mapeo de fallos: `ConnectError`/`ConnectTimeout` → `502
  MICROSERVICIO_INALCANZABLE`, `Read/WriteTimeout` → `504 TIEMPO_AGOTADO`,
  `PoolTimeout` → `503 GATEWAY_SATURADA`.
- **Brecha 1:** el timeout es el mismo para los cuatro servicios (salvo el
  prefijo `evidencias`). No se puede, por ejemplo, darle más margen a MS3 sin
  dárselo también a MS1.
- **Brecha 2:** el OpenAPI documenta `Retry-After` en el `503`, pero la Gateway
  **no** lo envía; tampoco en `502` ni `504`. El cliente no sabe cuándo
  conviene reintentar.

### 2.2 Entre microservicios

| Llamada | Para qué | Cliente | Timeout | Retry |
|---|---|---|---|---|
| MS2 → MS3 `GET /presupuestos/{id}/envio-inicial`, `/decisiones/{id}` y `/ordenes/{id}/primera-aprobacion` | Verificar el hecho antes de cambiar el estado de la orden | `httpx.get` | `MS2_MS3_TIMEOUT_SEGUNDOS` = 3 s | No |
| MS3 → MS2 `GET /ordenes/{id}` | ¿La orden es visible para el usuario? | `httpx.get` | `MS3_MS2_TIMEOUT_SEGUNDOS` = 3 s | No |
| MS3 → MS2 `POST /ordenes/{id}/decisiones-presupuesto` y `/envios-presupuesto` | Aplicar la decisión o el envío en la orden | `httpx.post` | 3 s | No (reintento **manual** idempotente) |
| MS4 → MS2 `GET /ordenes/{id}` | Verificar la orden antes de guardar evidencia | `httpx.get` | `MS4_MS2_TIMEOUT_SEGUNDOS` = 3 s | No |
| MS4 → MS3 `GET /presupuestos/{id}` | Verificar que el presupuesto es de la orden | `httpx.get` | `MS4_MS3_TIMEOUT_SEGUNDOS` = 3 s | No |

Todos traducen "sin conexión / timeout / respuesta inesperada" a un `503` propio
con `{"detail": ...}` y **no** dejan escrituras a medias:

- MS3 guarda primero la decisión y, si MS2 no confirma, responde `503` con
  `decision_id` y la ruta de reintento (`POST
  /presupuestos/decisiones/{id}/aplicacion`). El reintento es idempotente:
  MS2 registra la aplicación por referencia única en el historial.
- MS4 compensa la subida (borra el objeto y la fila) si MS2/MS3 no responden.
- Los movimientos de inventario de MS3 son idempotentes por `clave_operacion`.

Es decir: **la idempotencia ya está resuelta en el dominio**; lo que falta es
ordenar los timeouts y comunicar mejor cuándo reintentar.

### 2.3 Presupuestos de tiempo (peor caso)

```
Gateway ──15 s──► MS3 POST .../decision
                   └─3 s─► MS2 POST /ordenes/{id}/decisiones-presupuesto
                            └─3 s─► MS3 GET /presupuestos/decisiones/{id}

Gateway ──60 s──► MS4 POST /evidencias
                   ├─3 s─► MS2 GET /ordenes/{id}
                   ├─3 s─► MS3 GET /presupuestos/{id}
                   └─────► MinIO (subida del archivo)
```

- MS3 → MS2 (3 s) envuelve a MS2 → MS3 (3 s): si MS3 tarda casi 3 s en
  responderle a MS2, el timeout de MS3 vence primero. No rompe consistencia
  (MS3 responde `503` con la decisión guardada y el reintento la aplica), pero
  conviene saberlo: **el timeout exterior debe ser mayor que el interior**.
- Gateway → MS3 (15 s) cubre con holgura 3 s + 3 s + trabajo local.
- Gateway → MS4 (60 s) cubre 3 s + 3 s + la subida.
- Gateway → MS1: no tiene dependencias aguas abajo; el login con bcrypt tarda
  décimas de segundo. 15 s es más de lo necesario: un MS1 colgado retiene
  conexiones de la Gateway más tiempo del útil.

### 2.4 Frontend

`frontend/src/infrastructure/config/apiClient.ts` (axios) **no** define timeout
ni reintentos: espera lo que tarde la Gateway. Está bien que no reintente
escrituras por su cuenta (la Gateway ya reintenta al conectar); la vista ya
muestra estados de error reintentables (`asyncCollection.ts`).

---

## 3. Patrones evaluados

| Patrón | ¿Lo aplicamos? | Por qué |
|---|---|---|
| Timeouts por fase (connect/read/write/pool) | **Sí, ya está** | Distingue "no llegó" (502) de "llegó y tardó" (504). |
| Timeout **por servicio** | **Sí (Semana 7)** | Cada servicio tiene un presupuesto distinto (§2.3). Se configura por entorno, con los valores actuales como respaldo. |
| Retry al conectar (1 vez) | **Sí, ya está** | Seguro para cualquier método: la petición no salió. |
| Retry de lectura / 5xx en la Gateway | **No** | Duplicaría escrituras y amplifica la carga. Los reintentos de negocio ya existen y son idempotentes (rutas `.../aplicacion`, `clave_operacion`). |
| Retry entre microservicios | **No** | Reintentar en dos capas multiplica las llamadas (Gateway × MS3 × MS2). El usuario reintenta con la ruta idempotente. |
| `Retry-After` en 502/503/504 | **Sí (Semana 7)** | RFC 9110 §10.2.3: le dice al cliente cuántos segundos esperar. Estandariza la respuesta sin cambiar el cuerpo que ya lee el frontend. |
| Backoff con jitter | **En el cliente** (recomendación) | La Gateway no reintenta; si el frontend o la app móvil reintentan un `GET`, deben respetar `Retry-After` y agregar jitter. |
| Circuit breaker | **No por ahora** | En Vercel cada instancia serverless tiene su propia memoria: un breaker en memoria no se comparte y se reinicia en cada arranque en frío. Con timeouts cortos y health checks el beneficio es bajo. Se reevalúa si hay tráfico real. |
| Bulkhead (pool por servicio) | **No por ahora** | Un solo pool de 100 conexiones basta para el volumen del curso; el `PoolTimeout` ya devuelve `503` en vez de colgar. |
| Health check por dependencia | **Sí (Semana 7)** | Diagnóstico por servicio: proceso, base y (MS4) almacenamiento por separado, con latencia. |

---

## 4. Decisiones

> **Decisión R1 — Timeout de lectura/escritura por servicio, configurable.**
> Variables opcionales `GATEWAY_MS<n>_TIMEOUT_SECONDS`. Si no se definen se
> usan los valores generales (`GATEWAY_TIMEOUT_READ_SECONDS`/`WRITE`, 15 s) y
> 60 s para `evidencias`, así que el comportamiento por defecto no cambia.
> Recomendado: MS1 10 s, MS2 15 s, MS3 15 s, MS4 60 s. Regla: el timeout de la
> Gateway hacia un servicio debe ser **mayor** que la suma de los timeouts de
> ese servicio hacia sus dependencias (§2.3). `connect` (3 s) y `pool` (5 s)
> siguen siendo globales: no dependen del servicio destino.

> **Decisión R2 — Sin reintentos nuevos.** Se mantiene un único reintento al
> conectar en la Gateway y ninguno entre microservicios. Reintentar escrituras
> es responsabilidad del usuario mediante las rutas idempotentes que ya existen.

> **Decisión R3 — `Retry-After` en los errores de disponibilidad.** La Gateway
> agrega `Retry-After` (segundos, `GATEWAY_RETRY_AFTER_SECONDS`, 5 por defecto)
> a sus `502`, `503` y `504`. El cuerpo `ErrorRespuesta` no cambia (el frontend
> lee `detail`) y los errores generados por la Gateway además salen con
> `Cache-Control: no-store`, para que ningún intermediario cachee un error
> transitorio.

> **Decisión R4 — Log de fallos con servicio y timeout aplicado.** Cada fallo
> de red se registra con el nombre público del servicio (`ms3_presupuestos`),
> la excepción y el `request_id`; nunca la URL interna. Así un `504` se cruza
> rápido con el health check del mismo servicio.

> **Decisión R5 — Diagnóstico por servicio.** Nuevo
> `GET /api/health/servicios/{servicio}` que comprueba por separado el proceso
> (`/health`), la base (`/health/db`) y, en MS4, el almacenamiento
> (`/health/storage`), con latencia, el timeout que la Gateway aplica a ese
> servicio y sus prefijos. `GET /api/health/servicios` (agregado) se mantiene
> igual para no romper el monitoreo existente.

> **Decisión R6 — Recomendación a los clientes.** Web y móvil: solo reintentar
> automáticamente `GET` ante `502/503/504`, como máximo 2 veces, esperando
> `Retry-After` (o 1 s, 2 s) con jitter. Nunca reintentar `POST`/`PUT`/`PATCH`
> automáticamente: usar la ruta de reintento que devuelve el `503` de MS3.

---

## 5. Cómo se prueba

- Timeouts por servicio: `respx` simula `ReadTimeout` hacia un servicio y se
  verifica el `504` con `Retry-After`; se comprueba con `monkeypatch` que el
  `httpx.Timeout` aplicado a cada prefijo sale del servicio correcto.
- Diagnóstico: `respx` simula combinaciones (proceso ok y base caída, MS4 sin
  almacenamiento, servicio inalcanzable) y se verifican estado, código HTTP y
  que no se filtre ninguna URL interna.
- Smoke tests: un request por prefijo de la Gateway contra los cuatro apps
  reales (en proceso) y un script para correr lo mismo contra un entorno
  levantado.

---

## 6. Resumen de decisiones

| # | Decisión | Se aplica en |
|---|---|---|
| R1 | Timeout de lectura/escritura por servicio (`GATEWAY_MS<n>_TIMEOUT_SECONDS`), con respaldo en los generales. | Configurar timeouts por servicio |
| R2 | Sin reintentos nuevos: 1 al conectar en la Gateway, 0 entre servicios. | Configurar timeouts por servicio |
| R3 | `Retry-After` en 502/503/504 y `Cache-Control: no-store` en errores de la Gateway. | Respuestas estandarizadas |
| R4 | Logs de fallos con servicio, excepción y `request_id`, sin URLs internas. | Respuestas estandarizadas |
| R5 | `GET /api/health/servicios/{servicio}`: proceso, base y almacenamiento por separado. | Comprobación de disponibilidad |
| R6 | Clientes: reintentar solo `GET`, máx. 2, respetando `Retry-After` con jitter. | Documentación (frontend y móvil) |

## Referencias

- HTTPX — *Timeouts* y *Transports* (reintentos de conexión):
  <https://www.python-httpx.org/advanced/timeouts/>,
  <https://www.python-httpx.org/advanced/transports/>.
- RFC 9110 (HTTP Semantics) §10.2.3 `Retry-After`:
  <https://www.rfc-editor.org/rfc/rfc9110#section-10.2.3>.
- AWS Builders' Library — *Timeouts, retries, and backoff with jitter*:
  <https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/>.
- Google SRE Book — *Addressing Cascading Failures*:
  <https://sre.google/sre-book/addressing-cascading-failures/>.
- Microsoft Azure Architecture Center — *Circuit Breaker pattern*:
  <https://learn.microsoft.com/azure/architecture/patterns/circuit-breaker>.
- `docs/estudio-httpx-proxy.md` (Semana 4) y `docs/pruebas-comunicacion-gateway.md`.
