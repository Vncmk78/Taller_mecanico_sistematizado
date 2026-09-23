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
└── routers/
    ├── health.py    GET /  y  GET /api/health (endpoints propios de la Gateway)
    └── proxy.py     Reenvío de /api/* hacia los microservicios
```

## Cómo se enruta

La Gateway separa el primer segmento de `/api/*` y lo busca en la tabla
`RUTAS` (archivo `rutas.py`): `/api/auth/login` se reenvía a
`GATEWAY_MS1_URL` + `/auth/login`, y `/api/vehiculos?patente=AB1234` a
`GATEWAY_MS2_URL` + `/vehiculos?patente=AB1234`. El método, el body, el query
string y la cabecera `Authorization` (el JWT) llegan tal cual al
microservicio. Un prefijo sin microservicio responde `404`; si el servicio
destino está caído, `502`.

| Prefijo | Microservicio | Ejemplo |
|---|---|---|
| `auth` | MS1 (Autenticación y Usuarios) | `/api/auth/login` -> MS1 `/auth/login` |
| `vehiculos`, `vehiculo`, `ordenes`, `orden`, `clientes`, `mecanicos` | MS2 (Vehículos y Órdenes) | `/api/vehiculos` -> MS2 `/vehiculos` |
| `presupuestos`, `presupuesto`, `repuestos`, `proveedores`, `inventario` | MS3 (Presupuestos) | `/api/presupuestos` -> MS3 `/presupuestos` |
| `evidencias`, `evidencia` | MS4 (Evidencia Multimedia) | `/api/evidencias` -> MS4 `/evidencias` |

Los prefijos de MS3 y MS4 se conservan desde el inicio, pero su verificación
corresponde a la Semana 4.

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

- `GET http://localhost:8000/` — descripción y URLs de los microservicios.
- `GET http://localhost:8000/api/health` — `{"status": "ok", "servicio": "gateway"}`.
- `http://localhost:8000/docs` — Swagger de la Gateway.

## Variables de entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `GATEWAY_MS1_URL` | `http://localhost:8001` | MS1 Autenticación y Usuarios |
| `GATEWAY_MS2_URL` | `http://localhost:8002` | MS2 Vehículos y Órdenes |
| `GATEWAY_MS3_URL` | `http://localhost:8003` | MS3 Presupuestos, Repuestos y Proveedores |
| `GATEWAY_MS4_URL` | `http://localhost:8004` | MS4 Evidencia Multimedia |
| `GATEWAY_REQUEST_TIMEOUT_SECONDS` | `30` | Espera máxima a un microservicio |
| `GATEWAY_CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos (coma o JSON) |
| `GATEWAY_CORS_ALLOW_CREDENTIALS` | `true` | Permite cookies/Authorization cross-origin |

## Pruebas

```bash
pytest tests/test_gateway_estructura.py tests/test_gateway_rutas.py tests/test_gateway_formato.py -v
```
