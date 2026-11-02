# Variables de entorno y direcciones internas de los servicios

Semana 7 · Bastián Liempi · Taller de Integración II (Grupo 10)

Referencia única de **qué variable configura qué** en el SGTM y **cómo se
encuentran los servicios entre sí**, en local, con Docker y en Vercel. Los
valores por defecto salen del código (`*/config.py`); `backend/.env.example`
trae una copia lista para usar en desarrollo.

> `.env` nunca se sube al repositorio. Las claves (`*_JWT_SECRET_KEY`,
> `*_S3_SECRET_KEY`, DSN con contraseña) solo viven en `.env` local o en las
> variables de entorno de Vercel.

---

## 1. Mapa de direcciones

### 1.1 Local (desarrollo)

| Componente | Dirección | Arranque (desde `backend/`, salvo el frontend) |
|---|---|---|
| Frontend (Vite) | `http://localhost:5173` | `cd frontend && npm run dev` (proxy `/api` → `:8000`) |
| API Gateway | `http://localhost:8000` | `uvicorn gateway.main:app --reload --port 8000` |
| MS1 Autenticación y Usuarios | `http://localhost:8001` | `uvicorn services.ms1_auth.main:app --reload --port 8001` |
| MS2 Vehículos y Órdenes | `http://localhost:8002` | `uvicorn services.ms2_taller.main:app --reload --port 8002` |
| MS3 Presupuestos e Inventario | `http://localhost:8003` | `uvicorn services.ms3_presupuestos.main:app --reload --port 8003` |
| MS4 Evidencia Multimedia | `http://localhost:8004` | `uvicorn services.ms4_evidencias.main:app --reload --port 8004` |
| PostgreSQL MS1..MS4 (Docker) | `localhost:5433` .. `localhost:5436` | `docker compose up -d db_ms1 db_ms2 db_ms3 db_ms4` |
| MinIO API S3 / consola | `http://localhost:9000` / `http://localhost:9001` | `docker compose up -d minio minio_init` |

### 1.2 Quién llama a quién

```
Web / Móvil ──► Gateway :8000 ──GATEWAY_MS1_URL──► MS1 :8001
                              ├─GATEWAY_MS2_URL──► MS2 :8002 ──MS2_MS3_URL──► MS3
                              ├─GATEWAY_MS3_URL──► MS3 :8003 ──MS3_MS2_URL──► MS2
                              └─GATEWAY_MS4_URL──► MS4 :8004 ──MS4_MS2_URL──► MS2
                                                             ├─MS4_MS3_URL──► MS3
                                                             └─MS4_S3_ENDPOINT─► MinIO :9000
```

| Origen → destino | Variable | Por defecto | Para qué |
|---|---|---|---|
| Gateway → MS1 | `GATEWAY_MS1_URL` | `http://localhost:8001` | Prefijo `/api/auth` |
| Gateway → MS2 | `GATEWAY_MS2_URL` | `http://localhost:8002` | `/api/vehiculos`, `/api/ordenes` (+ alias) |
| Gateway → MS3 | `GATEWAY_MS3_URL` | `http://localhost:8003` | `/api/presupuestos`, `/api/repuestos`, `/api/proveedores`, `/api/inventario` |
| Gateway → MS4 | `GATEWAY_MS4_URL` | `http://localhost:8004` | `/api/evidencias` |
| MS2 → MS3 | `MS2_MS3_URL` | `http://localhost:8003` | Verificar envío inicial, decisión y primera aprobación de presupuesto |
| MS3 → MS2 | `MS3_MS2_URL` | `http://localhost:8002` | Visibilidad de la orden; aplicar decisión y envío inicial |
| MS4 → MS2 | `MS4_MS2_URL` | `http://localhost:8002` | Visibilidad de la orden antes de guardar evidencia |
| MS4 → MS3 | `MS4_MS3_URL` | `http://localhost:8003` | Orden a la que pertenece un presupuesto |
| MS4 → almacenamiento | `MS4_S3_ENDPOINT` | `http://localhost:9000` | Subida y verificación del bucket |

Las llamadas entre microservicios reenvían el **mismo JWT** del usuario
(`Authorization: Bearer ...`); no hay credenciales de servicio a servicio.

### 1.3 Vercel (producción, `https://tallerconect.vercel.app`)

Un solo proyecto con seis servicios (`vercel.json`):

| Servicio Vercel | Entrypoint | Ruta pública | Dirección interna |
|---|---|---|---|
| `frontend` | Vite | `/` | — |
| `backend` (Gateway) | `gateway.main:app` | `/api/*`, `/docs`, `/openapi.json` | — |
| `ms-auth` | `services.ms1_auth.main:app` | `/ms1/*` | Binding → `GATEWAY_MS1_URL` |
| `ms-taller` | `services.ms2_taller.main:app` | `/ms2/*` | Binding → `GATEWAY_MS2_URL`, `MS3_MS2_URL`, `MS4_MS2_URL` |
| `ms-presupuestos` | `services.ms3_presupuestos.main:app` | `/ms3/*` | Binding → `GATEWAY_MS3_URL`, `MS4_MS3_URL` |
| `ms-evidencias` | `services.ms4_evidencias.main:app` | `/ms4/*` | Binding → `GATEWAY_MS4_URL` |

Las URLs internas **no se escriben a mano**: los *bindings* de `vercel.json`
(`"type": "service", "format": "url"`) inyectan la variable con la dirección
interna del servicio al desplegar. Las rutas `/ms1..ms4/*` exponen cada
servicio directo (Swagger y health checks) y se reescriben a `/` dentro del
servicio.

> **Pendiente detectado (Semana 7):** `ms-taller` no declara un binding para
> `MS2_MS3_URL`. Si esa variable no está definida a mano en Vercel, MS2 usa el
> valor por defecto (`http://localhost:8003`) y las verificaciones MS2 → MS3
> (envío inicial, decisiones y primera aprobación de presupuesto) responden
> `503`. Solución propuesta: agregar en `vercel.json`, servicio `ms-taller`,
> `"bindings": [{ "type": "service", "service": "ms-presupuestos", "format": "url", "env": "MS2_MS3_URL" }]`.

---

## 2. Variables por componente

Convención: cada componente lee solo las variables con **su prefijo**
(`GATEWAY_`, `MS1_` … `MS4_`), vía `pydantic-settings`, desde el entorno o desde
`backend/.env`. Una variable de otro prefijo se ignora.

### 2.1 API Gateway (`gateway/config.py`, prefijo `GATEWAY_`)

| Variable | Por defecto | Uso |
|---|---|---|
| `GATEWAY_MS1_URL` … `GATEWAY_MS4_URL` | `http://localhost:8001` … `8004` | Dirección interna de cada microservicio |
| `GATEWAY_TIMEOUT_CONNECT_SECONDS` | `3.0` | Conectar a un servicio (si no, `502`) |
| `GATEWAY_TIMEOUT_READ_SECONDS` | `15.0` | Esperar la respuesta (si no, `504`) |
| `GATEWAY_TIMEOUT_WRITE_SECONDS` | `15.0` | Enviar el body (si no, `504`) |
| `GATEWAY_TIMEOUT_POOL_SECONDS` | `5.0` | Esperar conexión libre del pool (si no, `503`) |
| `GATEWAY_TIMEOUT_ARCHIVOS_SECONDS` | `60.0` | read/write del prefijo `evidencias` |
| `GATEWAY_MS1_TIMEOUT_SECONDS` … `GATEWAY_MS4_TIMEOUT_SECONDS` | vacío | read/write propio del servicio; prioridad sobre los anteriores (recomendado 10 / 15 / 15 / 60) |
| `GATEWAY_RETRY_AFTER_SECONDS` | `5` | Cabecera `Retry-After` de los `502/503/504` de la Gateway |
| `GATEWAY_HEALTH_TIMEOUT_SECONDS` | `2.0` | Timeout por comprobación en `/api/health/servicios*` (en Vercel se recomienda `5` por los arranques en frío) |
| `GATEWAY_MAX_BODY_BYTES` | `1048576` | Límite de body de los prefijos JSON (1 MiB) |
| `GATEWAY_MAX_BODY_ARCHIVOS_BYTES` | `12582912` | Límite de body de `evidencias` (12 MiB) |
| `GATEWAY_CORS_ORIGINS` | `http://localhost:5173,http://localhost:8000` | Orígenes permitidos (CSV o JSON) |
| `GATEWAY_CORS_ORIGIN_REGEX` | `https://[a-z0-9-]+\.vercel\.app` | Previews de Vercel; vacío la desactiva |
| `GATEWAY_CORS_ALLOW_CREDENTIALS` | `true` | Cookies/Authorization cross-origin |
| `GATEWAY_SERVICE_NAME` | `gateway` | Nombre en logs y en `/api/health` |

### 2.2 Comunes a MS1..MS4 (`shared/config.py`, con el prefijo de cada servicio)

| Variable (ej. MS1) | Por defecto | Uso |
|---|---|---|
| `MS1_DATABASE_URL` | `postgresql+psycopg://taller:taller@localhost:5433/taller_ms1` (MS2 `:5434/taller_ms2`, MS3 `:5435/taller_ms3`, MS4 `:5436/taller_ms4`) | Base propia del servicio. En Neon agregar `?sslmode=require` |
| `MS1_DB_ECHO` | `false` | Imprime el SQL (solo depurar) |
| `MS1_DB_POOL_SIZE` / `MS1_DB_MAX_OVERFLOW` | `5` / `10` | Pool de conexiones |
| `MS1_SERVICE_NAME` | nombre del servicio | Logs y `/health` |
| `MS1_JWT_SECRET_KEY` | **obligatoria** (≥ 32 caracteres) | Firma HS256. **La misma** en MS1, MS2, MS3 y MS4 |
| `MS1_JWT_ALGORITHM` | `HS256` | Único algoritmo admitido |

### 2.3 Propias de cada microservicio

| Servicio | Variable | Por defecto | Uso |
|---|---|---|---|
| MS1 | `MS1_JWT_EXPIRE_MINUTES` | `60` | Vigencia del token |
| MS1 | `MS1_LOGIN_MAX_INTENTOS` | `5` | Fallos seguidos antes del bloqueo |
| MS1 | `MS1_LOGIN_BLOQUEO_MINUTOS` | `15` | Duración del bloqueo |
| MS2 | `MS2_MS3_URL` | `http://localhost:8003` | Dirección de MS3 |
| MS2 | `MS2_MS3_TIMEOUT_SEGUNDOS` | `3.0` (máx. 30) | Timeout MS2 → MS3 |
| MS2 | `MS2_TIMEZONE` | `America/Santiago` | Día calendario del cupo diario de ingresos |
| MS3 | `MS3_MS2_URL` | `http://localhost:8002` | Dirección de MS2 |
| MS3 | `MS3_MS2_TIMEOUT_SEGUNDOS` | `3.0` (máx. 30) | Timeout MS3 → MS2 |
| MS4 | `MS4_MS2_URL` / `MS4_MS3_URL` | `:8002` / `:8003` | Direcciones de MS2 y MS3 |
| MS4 | `MS4_MS2_TIMEOUT_SEGUNDOS` / `MS4_MS3_TIMEOUT_SEGUNDOS` | `3.0` | Timeouts MS4 → MS2/MS3 |
| MS4 | `MS4_S3_ENDPOINT` | `http://localhost:9000` | API S3 (MinIO) interna |
| MS4 | `MS4_S3_PUBLIC_ENDPOINT` | vacío (= `S3_ENDPOINT`) | Host con el que se firman las URLs de descarga; en producción el dominio público |
| MS4 | `MS4_S3_ACCESS_KEY` / `MS4_S3_SECRET_KEY` | `ms4-evidencias` / (desarrollo) | Usuario S3 con permisos solo sobre el bucket |
| MS4 | `MS4_S3_BUCKET` / `MS4_S3_REGION` / `MS4_S3_SECURE` | `evidencias` / `us-east-1` / `false` | Bucket, región y HTTPS |
| MS4 | `MS4_URL_DESCARGA_TTL_SECONDS` | `300` (30–3600) | Vigencia de la URL prefirmada |
| MS4 | `MS4_TIPOS_PERMITIDOS` | JPG, PNG, WEBP, MP4, MOV | Lista blanca (JSON) |
| MS4 | `MS4_MAX_BYTES_FOTO` / `MS4_MAX_BYTES_VIDEO` | 10 MiB / 100 MiB | Tamaño máximo por tipo |
| MS4 | `MS4_LOG_LEVEL` | `INFO` | Nivel de logs (nunca registran JWT ni URLs firmadas) |

### 2.4 Infraestructura local (Docker Compose)

| Variable | Por defecto | Uso |
|---|---|---|
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | `admin-local` / `cambia-esta-clave-local` | Administrador de MinIO (solo `minio_init`) |
| Usuario/clave PostgreSQL | `taller` / `taller` | Fijos en `docker-compose.yml` (solo desarrollo) |

### 2.5 Frontend (`frontend/.env`)

| Variable | Por defecto | Uso |
|---|---|---|
| `VITE_API_URL` | `/api` | Base de las llamadas. En local el proxy de Vite reenvía `/api` a `:8000`; en Vercel la misma ruta llega a la Gateway |

---

## 3. Qué configurar en cada entorno

| Entorno | Obligatorio | Recomendado |
|---|---|---|
| Local | `MS1..MS4_JWT_SECRET_KEY` (la misma), DSN locales si no usas los puertos 5433–5436 | Copiar `backend/.env.example` a `backend/.env` |
| Vercel | `MS1..MS4_DATABASE_URL` (Neon, `sslmode=require`), `MS1..MS4_JWT_SECRET_KEY` (la misma), `MS4_S3_*` si se usarán evidencias | `GATEWAY_CORS_ORIGINS`, `GATEWAY_HEALTH_TIMEOUT_SECONDS=5`, `MS2_MS3_URL` (ver pendiente §1.3) |
| Pruebas (pytest) | Ninguna: `tests/conftest.py` fija claves y SQLite de prueba | — |

## 4. Cómo comprobar la configuración

- `GET /api/health/servicios`: los cuatro deben estar `ok` (Gateway bien
  apuntada y bases accesibles).
- `GET /api/health/servicios/{servicio}`: si uno falla, dice si es el proceso,
  la base o (MS4) el almacenamiento, y qué timeouts le aplica la Gateway.
- `python scripts/smoke_prefijos_gateway.py --gateway <url>`: recorre todos los
  prefijos (ver `docs/smoke-tests-gateway.md`).
- Un `401` en todo MS2/MS3/MS4 con un token recién emitido indica
  `*_JWT_SECRET_KEY` distintas entre servicios.
