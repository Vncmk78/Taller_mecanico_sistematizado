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
├── main.py          Crea la app, configura CORS y monta los routers
├── config.py        Variables de entorno (prefijo GATEWAY_)
├── rutas.py         Tabla de enrutamiento: prefijo -> microservicio
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
pytest tests/test_gateway_estructura.py tests/test_gateway_rutas.py -v
```
