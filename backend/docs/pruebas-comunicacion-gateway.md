# Pruebas de comunicación Gateway ↔ microservicios

Semana 4 · Bastián Liempi · Taller de Integración II (Grupo 10)

Los tests de `tests/test_gateway_rutas.py` usan **respx**: simulan a los
microservicios y prueban que la Gateway reenvía bien. Esta prueba es la
complementaria: con **todos los servicios levantados de verdad** se recorre el
flujo que usará el frontend (login en MS1 a través de la Gateway y uso del token
en MS2) y se compara el OpenAPI publicado por la Gateway con el de cada
microservicio.

```
Frontend / script → Gateway :8000 → MS1 :8001 (auth)
                                  → MS2 :8002 (vehículos y órdenes)
                                  → MS3 :8003 (presupuestos)
                                  → MS4 :8004 (evidencias)
```

## Qué debe calzar entre MS1 (Deris) y el resto

El token lo **emite MS1** y lo **validan MS2 y MS4** (`shared/auth.py`). Para que
la cadena funcione:

1. **Misma clave**: `MS1_JWT_SECRET_KEY` = `MS2_JWT_SECRET_KEY` =
   `MS4_JWT_SECRET_KEY` en `.env` (si difieren, MS2 responde `401` a todo).
2. **Mismos claims**: `sub` (usuario_id) y `roles`, algoritmo `HS256`.
3. **Mismo MS1**: la Gateway apunta a `backend/services/ms1_auth` en `:8001`
   (`GATEWAY_MS1_URL`).
4. **Mismos contratos**: `POST /auth/register`, `POST /auth/login`,
   `GET /auth/me` con los campos que publica la Gateway en `/openapi.json`.

## Cómo levantar todo (local)

Desde `backend/`, con Docker Desktop abierto y un `.env` (copia de
`.env.example`, la misma clave en las tres variables `*_JWT_SECRET_KEY`):

```bash
# 1) Bases de datos, migraciones y usuarios de prueba
docker compose up -d db_ms1 db_ms2 db_ms3 db_ms4
python -m alembic -c services/ms1_auth/alembic.ini upgrade head
python -m alembic -c services/ms2_taller/alembic.ini upgrade head
python scripts/seed_usuarios_prueba.py

# 2) Un servicio por terminal
python -m uvicorn services.ms1_auth.main:app --port 8001
python -m uvicorn services.ms2_taller.main:app --port 8002
python -m uvicorn services.ms3_presupuestos.main:app --port 8003
python -m uvicorn services.ms4_evidencias.main:app --port 8004
python -m uvicorn gateway.main:app --port 8000

# 3) Pruebas
python scripts/prueba_comunicacion.py
python scripts/revisar_openapi.py
```

Usuarios de prueba (creados por el seed): `cliente@pruebas.cl`,
`mecanico@pruebas.cl`, `administrador@pruebas.cl` (claves en
`scripts/seed_usuarios_prueba.py`).

## Qué verifica `scripts/prueba_comunicacion.py`

| # | Paso | Esperado |
|---|---|---|
| 1 | `GET /api/health` de la Gateway | 200 |
| 2 | `GET /health` de MS1, MS2, MS3 y MS4 (directo a su puerto) | 200 |
| 3 | Login del cliente y del administrador vía `/api/auth/login` | 200 + `access_token` |
| 4 | Login con contraseña incorrecta | 401 |
| 5 | `/api/auth/me` con el token del cliente | 200 y el email correcto |
| 6 | `/api/vehiculos` con el token emitido por MS1 | 200 (MS2 acepta el token: clave compartida) |
| 7 | `/api/vehiculos` con un token alterado | 401 |
| 8 | `/api/ordenes` con el token del administrador | 200 |
| 9 | `/api/vehiculos` sin token | 401 |
| 10 | `/api/presupuestos` y `/api/evidencias` | 404 **del microservicio** (MS3/MS4 alcanzables; sus endpoints llegan en la Semana 5) |
| 11 | `/api/noexiste` | 404 de la Gateway con el formato común (`error.codigo`) |
| 12 | `X-Request-ID` enviado por el cliente | vuelve igual en la respuesta |
| 13 | `GET /api/health/servicios` vía Gateway | 200 con los 4 microservicios en `"ok"` |

## Qué verifica `scripts/revisar_openapi.py`

Para cada operación que la Gateway documenta bajo `/api/*` (contratos de
`gateway/contratos`), descarga el `/openapi.json` del microservicio dueño del
prefijo y comprueba que la ruta y el método existan y que los campos del body
y de la respuesta exitosa sean los mismos. Cualquier diferencia es una
discrepancia de contrato que el frontend heredaría.

## Pruebas de integración automáticas

Además de la prueba manual con servicios levantados hay tres niveles de tests
automáticos que cubren la comunicación Gateway ↔ microservicios:

| Nivel | Archivo | Chiste | Rápido |
|---|---|---|---|
| Gateway simulada (respx) | `tests/test_gateway_rutas.py`, `tests/test_gateway_errores_proxy.py` | Los microservicios son respuestas respx; se prueban enrutamiento, cabeceras y errores de la Gateway | Sí |
| Límites de body de la Gateway (respx) | `tests/test_gateway_evidencias.py` | 413/400 antes de tocar al microservicio, corte en streaming, límites configurables y unidades de `limite_para`/`timeout_para` | Sí |
| Integración in-process | `tests/test_integracion_prefijos.py` | Gateway REAL + los 4 apps REALES conectados por `httpx.ASGITransport` por URL base, cada uno con SQLite en memoria | Sí |
| Integración in-process (evidencias) | `tests/test_gateway_evidencias.py` | Gateway REAL → app REAL de MS4 (SQLite en memoria, FakeS3, VerificadorPermiteTodo): subida multipart 201, request_id propagado, listado/descarga 200, 403 del cliente y 503 de MS4 a través de la Gateway | Sí |
| Servicios levantados | `scripts/prueba_comunicacion.py` | Red real + PostgreSQL + MinIO/S3 | No |

El nivel in-process (`tests/test_integracion_prefijos.py`) es el gemelo
automático del `prueba_comunicacion.py`: como los transports se cuelgan de las
mismas URLs (`GATEWAY_MS1_URL`... `GATEWAY_MS4_URL`) que usan los servicios
reales, el enrutamiento de `gateway.rutas` hace lo mismo que en producción. La
Gateway y los 4 microservicios ejecutan su código real (mismas rutas, schemas,
auth y motor SQLAlchemy); lo único simulado es la capa de red (se cambia el
transporte HTTPX por ASGI) y la base de datos (SQLite en memoria en vez de
PostgreSQL).

Para correrlo solo:

```bash
python -m pytest tests/test_integracion_prefijos.py -v
```

Qué cubre:

- **MS1**: registro público (`201`, solo rol `cliente`), login (`200` con token),
  `me` (`200`), login con contraseña incorrecta (`401`) y `me` sin token
  (`401` con `WWW-Authenticate`).
- **MS2**: flujo completo de vehículos con un token emitido por MS1 (`201/200/200`),
  falta de token (`401`), body inválido (`422` con `detail` en lista), vehículo
  de otro cliente (`404 "Vehículo no encontrado"`), órdenes como admin (`200
  []`) y token alterado (`401`).
- **MS3 y MS4**: sus prefijos responden `404 {"detail": "Not Found"}` propio del
  microservicio, sin la clave `error` que identifica al 404 de la Gateway
  (hasta la Semana 5 no tienen endpoints de negocio).
- **Transversales**: `GET /api/health/servicios` con los 4 en `"ok"`,
  `X-Request-ID` de ida y vuelta en una petición proxied, y `/api/noexiste`
  devolviendo el 404 en el formato común de la Gateway.
- **Por servicio**: una petición proxied responde algo que solo ese
  microservicio produce (perfil del usuario autenticado, el vehículo recién
  creado, el 404 del microservicio).

No usa respx a propósito: responder el código real de cada microservicio es
justamente lo que se quiere comprobar.

## Evidencias por la Gateway (Semana 5)

Subir y consultar evidencias usa el nivel in-process de `tests/test_gateway_evidencias.py`:
la Gateway REAL conectada a la app REAL de MS4 por `ASGITransport` (SQLite en
memoria, FakeS3, cliente S3 público que firma offline y `VerificadorPermiteTodo`,
pues la autorización contra MS2 es de `test_ms4_autorizacion_evidencias.py`).
El token lo acuña directamente la prueba con la clave JWT de MS4 (el fixture no
levanta MS1, igual que en los tests HTTP de MS4).

Casos y resultados:

| Caso | Resultado |
|---|---|
| `POST /api/evidencias` con `Content-Length` > 12 MiB | `413 CUERPO_DEMASIADO_GRANDE`, sin llamar a MS4, sin filtrar el límite |
| `POST /api/vehiculos` (JSON) con body > 1 MiB | `413 CUERPO_DEMASIADO_GRANDE`, sin llamar a MS2 |
| Body justo en el límite del prefijo | pasa (200/201) |
| Petición chunked sin `Content-Length` que excede | `413` (corte en el streaming, nunca acumula más del límite + un trozo) |
| `Content-Length` no numérica | `400 ERROR_HTTP` |
| Límites configurables (`monkeypatch` de settings) | el corte sigue a `GATEWAY_MAX_BODY_*` |
| Mecánico sube multipart por `/api/evidencias` | `201`, JSON sin `clave_objeto` ni `ordenes/`, `X-Request-ID` de ida y vuelta, fila con ese `request_id`, objeto en FakeS3 con `content_type` correcto |
| `GET /api/evidencias?orden_id=...` | `200` con los filtros de visibilidad de MS4 intactos |
| `GET /api/evidencias/{id}/descarga` | `200`, URL firmada (`minio.publico.test:9000`), `Cache-Control: no-store` y `X-Content-Type-Options: nosniff` llegan al cliente |
| Cliente intenta subir | `403` con el body JSON de MS4 tal cual (`detail`) |
| MinIO caído (MS4 tradujo el fallo de boto3) | `503` con el `detail` de MS4 a través de la Gateway |
| `timeout_para("evidencias")` | read/write = `GATEWAY_TIMEOUT_ARCHIVOS_SECONDS` (60 s) |

Para correrlo solo:

```bash
python -m pytest tests/test_gateway_evidencias.py -v
```

## Resultados

| Fecha | Entorno | Comunicación | OpenAPI | Notas |
|---|---|---|---|---|
| 2026-09-29 | Local, bases SQLite (verificación previa de los scripts) | 17/17 | 11 operaciones, sin discrepancias | Ensayo antes de la prueba conjunta |
| _pendiente_ | Local, PostgreSQL (Docker), con Deris | _/18 | _ | Prueba conjunta Gateway ↔ Autenticación |

## Coordinación con Deris (Autenticación)

- [ ] Confirmado que el MS1 oficial es `backend/services/ms1_auth` (puerto 8001).
- [ ] Confirmados los endpoints `POST /auth/register`, `POST /auth/login` y `GET /auth/me`.
- [ ] Confirmados los claims del token (`sub`, `roles`) y `HS256`.
- [ ] Prueba conjunta ejecutada: resultados registrados en la tabla de arriba.
