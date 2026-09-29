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
