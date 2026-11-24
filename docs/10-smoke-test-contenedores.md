# 10 — Construcción de contenedores y smoke test previo al despliegue

Semana 11 · Construir contenedores y ejecutar smoke test previo al despliegue.

## Para qué sirve

Un push a `main` publica las imágenes y **actualiza Kubero automáticamente**
(`docker-build.yml` → job *Actualizar Kubero al sha publicado*). Por eso
conviene comprobar **antes** del push que las imágenes construyen y que la
topología completa arranca sana. El smoke test hace eso en Docker local, con
los **mismos Dockerfile** que usa el workflow.

## Qué levanta

`backend/despliegue/compose.bd.yml` + `backend/despliegue/compose.smoke.yml`:

| Servicio | Imagen | Qué hace | Publicado en |
| --- | --- | --- | --- |
| `postgres` | `postgres:16` | 4 bases `sgtm_ms1..4`, un rol por servicio | `127.0.0.1:5460` |
| `migraciones` | `sgtm-backend:despliegue` | Migra MS1 → MS4 y termina | — |
| `minio` + `minio_init` | Chainguard MinIO + `mc` | Bucket privado `evidencias`, usuario y política de MS4 | no se publica |
| `ms1`…`ms4` | `sgtm-backend:despliegue` | Microservicios (`SGTM_SERVICIO=ms1..ms4`) | no se publican |
| `gateway` | `sgtm-backend:despliegue` | API Gateway | `127.0.0.1:8080` |
| `web` | `sgtm-web:despliegue` | Nginx + build de React, proxy `/api` → Gateway | `127.0.0.1:8081` |

Orden de arranque, usando el `HEALTHCHECK` de las imágenes en `depends_on`:

```
postgres (healthy) → migraciones (exit 0) → ms1..ms4 (healthy) → gateway (healthy) → web (healthy)
minio (healthy) → minio_init (exit 0) ──────────┘ (solo ms4)
```

La red interna reproduce Kubero: los servicios se hablan por nombre
(`http://ms1:8000`, `http://gateway:8000`), igual que `http://ms1-kuberoapp` allá.

## Cómo ejecutarlo

Requisitos: Docker Desktop abierto, Git Bash y el entorno virtual de `backend/`
activado (para los scripts de verificación).

```bash
cd backend
source .venv/Scripts/activate        # Windows (Git Bash)
bash scripts/smoke_contenedores.sh            # construye, levanta y verifica
bash scripts/smoke_contenedores.sh --bajar    # igual y al final apaga los contenedores
```

La primera vez genera `despliegue/.env.despliegue` con claves aleatorias
(`inicializar_bd.py configurar`, fuera de Git). Sale con **0** si todo pasa
(*"SMOKE TEST OK: listo para hacer push a main"*) y con **1** si algo falla.

## Qué verifica

| # | Paso | Criterio de éxito |
| --- | --- | --- |
| 0 | Requisitos | Docker responde; existe `.env.despliegue` |
| 1 | Construcción | `sgtm-backend:despliegue` y `sgtm-web:despliegue` construyen sin error (se informa el tiempo) |
| 2 | Arranque | `docker compose up -d` sin error |
| 3 | Healthchecks | `ms1`…`ms4`, `gateway` y `web` en `healthy`; `migraciones` termina con 0 |
| 4 | Salud punta a punta | `verificar_salud.py` → 6/6 (Gateway, 4 bases, MinIO) |
| 5 | Web | `/`, `/healthz` y `/api/health/servicios` (proxy Nginx) responden 200 |
| 6 | Enrutamiento | `smoke_prefijos_gateway.py`: cada prefijo `/api/*` llega a su microservicio, `X-Request-ID` y 404 de la Gateway |

Reportes JSON en `backend/salidas-integracion/` (`smoke-contenedores.json`,
`smoke-prefijos.json`; carpeta ignorada por Git).

## Comandos útiles

```bash
# desde backend/
C="docker compose -f despliegue/compose.bd.yml -f despliegue/compose.smoke.yml --env-file despliegue/.env.despliegue"
$C ps                       # estado (healthy/unhealthy)
$C logs gateway             # logs de un servicio
$C down                     # apagar (conserva la base)
$C down -v                  # apagar y BORRAR la base local del smoke test
```

## Diferencias con Kubero

| Aspecto | Smoke test local | Kubero |
| --- | --- | --- |
| Imágenes | Construidas del código local | `ghcr.io/vncmk78/...:sha-<commit>` |
| PostgreSQL | Un contenedor con 4 bases | Addons PostgreSQL por servicio |
| MinIO | Desechable, sin publicar | App `minio` con PVC y dominio público |
| HTTPS | No (HTTP en 127.0.0.1) | TLS en el Ingress |
| Health | `HEALTHCHECK` de Docker | Probes de Kubernetes |
| Datos | Bases vacías (solo migraciones) | Datos de demostración |

## Evidencia

Pendiente de la primera ejecución: pegar aquí la salida de
`bash scripts/smoke_contenedores.sh` y `docker compose ... ps`.
