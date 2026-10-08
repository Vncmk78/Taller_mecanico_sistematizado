# API Gateway — SGTM

Único punto de entrada al backend. El frontend web (React) y la app móvil
(Integración IV) llaman a `/api/*` en la Gateway, y la Gateway reenvía cada
petición al microservicio que corresponde. No contiene reglas de negocio ni
accede a bases de datos: solo enruta.

```
Web / Móvil ──► API Gateway (:8000) ──► MS1 Auth           (:8001)
                                    ├─► MS2 Vehículos/OT   (:8002)
                                    ├─► MS3 Presupuestos   (:8003)
                                    └─► MS4 Evidencias     (:8004)
```

## Estructura

```
gateway/
├── main.py          Crea la app, configura CORS, middleware y handlers
├── config.py        Variables de entorno (prefijo GATEWAY_)
├── rutas.py         Tabla de enrutamiento: prefijo -> microservicio
├── esquemas.py      Modelos Pydantic del formato común (errores)
├── errores.py       Formato común de errores + middleware del 500 (dentro de CORS)
├── middleware.py    Cabecera X-Request-ID en cada petición
├── openapi.py       Reescribe el Swagger con los contratos reales de MS1, MS2 y MS4
├── openapi_ejemplos.py Ejemplos reales, respuestas comunes y X-Request-ID
├── contratos/       Copias de los contratos HTTP de MS1, MS2 y MS4 (para documentar)
└── routers/
    ├── health.py    GET /  y  GET /api/health (endpoints propios de la Gateway)
    └── proxy.py     Reenvío de /api/* hacia los microservicios
```

## Documentación

El Swagger de la Gateway publica los contratos reales que enruta (Auth,
Vehículos, Órdenes y Evidencias), con sus esquemas, ejemplos y el botón Authorize:

- `GET /docs` — Swagger UI.
- `GET /openapi.json` — esquema OpenAPI completo.
- [`docs/contratos-api-gateway.md`](../docs/contratos-api-gateway.md) — el
  documento que leen el equipo y la app móvil (contratos, ejemplos y pendientes).

`GET /docs` muestra un ejemplo por body y por respuesta, y las respuestas
reutilizables de `components.responses` (`NoAutenticado`, `ErrorInterno`,
`ServicioNoDisponible`, `GatewaySaturada` y `TiempoAgotado`). Los ejemplos reales,
los `X-Request-ID` y los de los health checks se agregan en
`openapi_ejemplos.py`, que es idempotente y nunca pisa los ejemplos de órdenes de
`shared/openapi_ordenes.py`. `tests/test_gateway_openapi_ejemplos.py` valida el
esquema con `openapi-spec-validator` y comprueba que cada ejemplo cumple su
esquema.

Los contratos viven en `gateway/contratos/` (la Gateway no importa código de
los microservicios). `tests/test_gateway_openapi.py` compara esas copias con
los esquemas reales de MS1 y MS2: si alguien cambia un campo, el test falla y
avisa que la documentación quedó desactualizada.

## Cómo se enruta

La Gateway separa el primer segmento de `/api/*` y lo busca en la tabla
`RUTAS` (archivo `rutas.py`): `/api/auth/login` se reenvía a
`GATEWAY_MS1_URL` + `/auth/login`, `/api/vehiculos` a `GATEWAY_MS2_URL` +
`/vehiculos` y `/api/ordenes/31/mecanico` a `GATEWAY_MS2_URL` +
`/ordenes/31/mecanico`. El método, el body, el query string y la cabecera
`Authorization` (el JWT) llegan tal cual al microservicio. Un prefijo sin
microservicio responde `404`; si el servicio destino está caído, `502`.

| Prefijo | Microservicio | Ejemplo |
|---|---|---|
| `auth` | MS1 (Autenticación y Usuarios) | `/api/auth/login` -> MS1 `/auth/login` |
| `vehiculos`, `vehiculo`, `ordenes`, `orden`, `clientes`, `mecanicos` | MS2 (Vehículos y Órdenes) | `/api/vehiculos` -> MS2 `/vehiculos` |
| `presupuestos`, `presupuesto`, `repuestos`, `proveedores`, `inventario` | MS3 (Presupuestos) | `/api/presupuestos` -> MS3 `/presupuestos` |
| `evidencias`, `evidencia` | MS4 (Evidencia Multimedia) | `/api/evidencias` -> MS4 `/evidencias` |

Los prefijos de MS3 y MS4 se conservan desde el inicio; desde la Semana 4 la
Gateway verifica el reenvío hacia ambos microservicios
(`tests/test_gateway_rutas.py`) y fija la convención: MS3 publica bajo sus
prefijos (`presupuestos`, `repuestos`, `proveedores`, `inventario`) y MS4 todo
bajo `evidencias`, nunca bajo `/ordenes/...` (ver
[`docs/contratos-api-gateway.md`](../docs/contratos-api-gateway.md)).

## Formato común

Contrato único de solicitudes, respuestas y errores de la Gateway.

### Solicitudes

- Cuerpo en JSON con `Content-Type: application/json`.
- La cabecera `Authorization: Bearer <jwt>` se reenvía tal cual al
  microservicio (ahí se valida).
- `X-Request-ID` es opcional: identifica una petición en los logs de la
  Gateway y del microservicio. Si no viene, o viene con más de 128 caracteres
  o con caracteres que no sean letras, números o guiones, la Gateway genera un
  UUID y lo usa.
- Límite de body por prefijo (checklist 4.2): 1 MiB para los prefijos JSON y
  12 MiB para `evidencias`. Superarlo responde `413` (`CUERPO_DEMASIADO_GRANDE`,
  mensaje genérico) sin leer el body ni llamar al microservicio;
  `Content-Length` no numérica responde `400`. El multipart conserva su
  `Content-Type` con el `boundary`. No hay streaming hacia MS4 (riesgo 4.3
  acotado por el límite): los videos van por el flujo C (POST prefirmado,
  Semana 6+).

El reenvío usa un único cliente HTTPX compartido (`gateway/cliente_http.py`),
creado de forma perezosa y cerrado en el lifespan de la app, con timeouts por
fase (conectar 3 s, leer/escribir 15 s, pool 5 s). El prefijo `evidencias` usa
read/write de 60 s porque sube archivos. Los fallos de red se mapean según la
decisión 2 del estudio: `ConnectError`/`ConnectTimeout` → 502,
`Read/WriteTimeout` → 504 y `PoolTimeout` → 503.

### Respuestas

- Éxitos y errores de los microservicios pasan **sin modificarse** (cuerpo y
  status code), incluido el `detail` de sus errores. La Gateway no envuelve ni
  toca lo que devuelve un microservicio.
- Toda respuesta lleva la cabecera `X-Request-ID` (la del cliente o la
  generada), y la misma se propaga hacia el microservicio.

### Errores de la propia Gateway

Los únicos errores que normaliza la Gateway (porque ella los genera) siguen
este cuerpo:

```json
{
  "detail": "mensaje legible para el frontend",
  "error": {
    "codigo": "RUTA_NO_ENCONTRADA",
    "estado": 404,
    "ruta": "/api/desconocido",
    "request_id": "a1b2c3d4-..."
  }
}
```

`detail` se mantiene en string de primer nivel porque
`frontend/src/infrastructure/api/errors.ts` lo lee con
`response.data.detail`. Códigos:

| Código | Estado | Cuándo |
|---|---|---|
| `RUTA_NO_ENCONTRADA` | 404 | Prefijo sin microservicio o ruta inexistente |
| `METODO_NO_PERMITIDO` | 405 | Método HTTP no soportado en la ruta |
| `MICROSERVICIO_INALCANZABLE` | 502 | El microservicio destino no responde (mensaje genérico, sin URL interna) |
| `TIEMPO_AGOTADO` | 504 | El microservicio recibió la petición pero tardó más que el timeout en responder |
| `GATEWAY_SATURADA` | 503 | El pool de conexiones de la Gateway está lleno |
| `CUERPO_DEMASIADO_GRANDE` | 413 | Body mayor al límite por prefijo (checklist 4.2); se responde sin leerlo ni llamar al microservicio |
| `ERROR_MICROSERVICIO` | (del ms) | 4xx/5xx del microservicio sin body JSON, reemplazado por el formato común |
| `ERROR_INTERNO` | 500 | Error no controlado (mensaje genérico, sin traza) |
| `ERROR_HTTP` | otro | Estado HTTP no previsto (p. ej. un 400) |

Los detalles de la Gateway están en español ("Ruta no encontrada",
"Método no permitido", etc.) para que el frontend los muestre tal cual.

El 500 se genera en `ManejoErroresMiddleware`, montado **por dentro de CORS**
(orden: `RequestId -> CORS -> ManejoErrores`): así la respuesta de error sale
con `Access-Control-Allow-Origin` y `X-Request-ID`, igual que cualquier otra
respuesta. La traza completa queda en el log del servidor (logger `gateway`),
asociada al `request_id`; el cliente solo recibe el mensaje genérico.

## Levantar la Gateway

Desde la carpeta `backend/`, con el entorno virtual activo:

```bash
uvicorn gateway.main:app --reload --port 8000
```

- `GET http://localhost:8000/` — descripción y prefijos `/api/*` que enruta.
- `GET http://localhost:8000/api/health` — `{"status": "ok", "servicio": "gateway"}`.
- `GET http://localhost:8000/api/health/servicios` — estado de los 4 microservicios.
- `http://localhost:8000/docs` — Swagger de la Gateway.

## Health checks

- `GET /api/health` — responde solo por la Gateway, sin consultar a los
  microservicios (lo usa Vercel y no puede depender de que estén arriba).
- `GET /api/health/servicios` — consulta `/health/db` de los cuatro
  microservicios en paralelo con el cliente HTTPX compartido y un timeout corto
  por servicio (`GATEWAY_HEALTH_TIMEOUT_SECONDS`, 2 s por defecto): un servicio
  caído no bloquea la respuesta agregada.

```json
{
  "status": "ok",
  "gateway": "ok",
  "servicios": {
    "ms1_auth": { "estado": "ok", "latencia_ms": 3 },
    "ms2_taller": { "estado": "ok", "latencia_ms": 4 },
    "ms3_presupuestos": { "estado": "ok", "latencia_ms": 2 },
    "ms4_evidencias": { "estado": "ok", "latencia_ms": 5 }
  }
}
```

Responde `200` con `"status": "ok"` si los cuatro están `ok`, y `503` con
`"status": "degradado"` si alguno no lo está. Estados por servicio: `ok`,
`sin_base` (el proceso responde pero su health/base falla; incluye
`codigo_http`), `tiempo_agotado` (superó el timeout) y `caido` (sin conexión).
Toda respuesta trae `Cache-Control: no-store` y `X-Request-ID`; el body no
expone URLs internas (los detalles de cada fallo quedan en el log del servidor).

## Variables de entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `GATEWAY_MS1_URL` | `http://localhost:8001` | MS1 Autenticación y Usuarios |
| `GATEWAY_MS2_URL` | `http://localhost:8002` | MS2 Vehículos y Órdenes |
| `GATEWAY_MS3_URL` | `http://localhost:8003` | MS3 Presupuestos, Repuestos y Proveedores |
| `GATEWAY_MS4_URL` | `http://localhost:8004` | MS4 Evidencia Multimedia |
| `GATEWAY_TIMEOUT_CONNECT_SECONDS` | `3.0` | Tiempo para conectar a un microservicio (si no, 502) |
| `GATEWAY_TIMEOUT_READ_SECONDS` | `15.0` | Espera entre bloques de la respuesta (si no, 504) |
| `GATEWAY_TIMEOUT_WRITE_SECONDS` | `15.0` | Espera al enviar el body (si no, 504) |
| `GATEWAY_TIMEOUT_POOL_SECONDS` | `5.0` | Espera por una conexión libre del pool (si no, 503) |
| `GATEWAY_TIMEOUT_ARCHIVOS_SECONDS` | `60.0` | read/write ampliados para el prefijo `evidencias` |
| `GATEWAY_MAX_BODY_BYTES` | `1048576` | Límite de body (bytes) para los prefijos JSON (1 MiB); superarlo responde `413` |
| `GATEWAY_MAX_BODY_ARCHIVOS_BYTES` | `12582912` | Límite de body (bytes) para `evidencias` (12 MiB: foto de 10 MB + margen del multipart) |
| `GATEWAY_HEALTH_TIMEOUT_SECONDS` | `2.0` | Timeout por servicio en `GET /api/health/servicios` |
| `GATEWAY_CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos (coma o JSON) |
| `GATEWAY_CORS_ALLOW_CREDENTIALS` | `true` | Permite cookies/Authorization cross-origin |

## Pruebas

```bash
pytest tests/test_gateway_estructura.py tests/test_gateway_rutas.py tests/test_gateway_formato.py tests/test_gateway_openapi.py tests/test_gateway_evidencias.py -v
```
