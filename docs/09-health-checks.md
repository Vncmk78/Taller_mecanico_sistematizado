# 09 — Health checks de los servicios desplegados

Semana 11 · Configurar health checks de servicios desplegados.

## Qué hay

| Capa | Dónde | Qué comprueba |
| --- | --- | --- |
| Proceso de cada microservicio | `GET /health` en MS1–MS4 | El proceso FastAPI responde |
| Base de cada microservicio | `GET /health/db` en MS1–MS4 | `SELECT 1` contra su base propia |
| Almacenamiento MS4 | `GET /health/storage` | El bucket de evidencias (MinIO/S3) responde |
| Gateway | `GET /api/health` | El proceso de la Gateway responde |
| Gateway → bases | `GET /api/health/servicios` | `/health/db` de los 4 servicios en paralelo (200 / 503) |
| Gateway → diagnóstico | `GET /api/health/servicios/{ms}` | Proceso, base y (MS4) almacenamiento con latencia |
| **Contenedor backend** (nuevo) | `HEALTHCHECK` en `Dockerfile` | Ejecuta `scripts/healthcheck_contenedor.py` |
| **Contenedor web** (nuevo) | `HEALTHCHECK` en `frontend/Dockerfile` | `wget` a `/healthz` de Nginx |
| **Verificación externa** (nuevo) | `scripts/verificar_salud.py` | Recorre todo lo anterior vía Gateway y entrega tabla/JSON |

## HEALTHCHECK de contenedores

Una sola imagen backend sirve para Gateway y MS1–MS4 (`SGTM_SERVICIO`). El
script `backend/scripts/healthcheck_contenedor.py` lee esa misma variable y
`PORT`, y consulta `/api/health` (gateway) o `/health` (ms1..ms4). Con
`SGTM_SERVICIO=migraciones` siempre sale 0 porque no levanta servidor.

- Intervalo 15 s, timeout 5 s, gracia inicial 20 s, 3 reintentos.
- Solo usa la biblioteca estándar: la imagen `python:slim` no trae curl.
- No consulta la base a propósito: un corte de la base no debe reiniciar el
  contenedor; eso se ve en `/api/health/servicios`.

`docker ps` / `docker compose ps` muestran el estado `healthy` / `unhealthy`.

## Verificación de salud (smoke test)

```bash
cd backend
python scripts/verificar_salud.py                                      # local (Gateway en :8000)
python scripts/verificar_salud.py --base https://api-tallerconnect.inf.uct.cl
python scripts/verificar_salud.py --base https://api-tallerconnect.inf.uct.cl --json salidas-integracion/salud.json
```

Sale con 0 si todo está OK y 1 si algo falla (sirve en CI o antes/después de desplegar).

## Evidencia (ambiente público, 20-11-2026)

```
Salud del backend SGTM — https://api-tallerconnect.inf.uct.cl
------------------------------------------------------------------------------
[ OK ] gateway              HTTP 200          ok
[ OK ] servicios (bases)    HTTP 200          ok
[ OK ] ms1_auth             HTTP 200          proceso=ok (10 ms), base=ok (15 ms)
[ OK ] ms2_taller           HTTP 200          proceso=ok (9 ms), base=ok (17 ms)
[ OK ] ms3_presupuestos     HTTP 200          proceso=ok (8 ms), base=ok (17 ms)
[ OK ] ms4_evidencias       HTTP 200          proceso=ok (11 ms), base=ok (48 ms), almacenamiento=ok (163 ms)
------------------------------------------------------------------------------
6/6 comprobaciones OK
```

## Pruebas

`backend/tests/test_healthchecks_despliegue.py` (19 casos): rutas por servicio,
configuración inválida, respuesta 200/500/sin servidor, códigos de salida,
presencia del `HEALTHCHECK` en ambos Dockerfile y el reporte de
`verificar_salud.py` con todo OK, con MS4 caído y sin conexión.
