# 02 — Despliegue en Kubero UCT

Este documento describe **cómo está montado** el ambiente y **cómo replicarlo**
si hay que reconstruirlo. Está escrito para alguien con acceso al panel de Kubero
y conocimientos básicos de contenedores.

- Panel: <https://kubero.inf.uct.cl>
- Pipeline: `tallerconnect`
- Fase: `Production`

> Kubero UCT **no construye imágenes**. Solo despliega imágenes ya publicadas en
> un registro. Por eso el repositorio incluye un workflow de GitHub Actions que
> publica las imágenes en GHCR y, al terminar, actualiza las 6 apps Docker al tag
> `sha-<commit>` recién publicado.

---

## 1. Requisitos previos

1. Cuenta con acceso al pipeline `tallerconnect` en el panel de Kubero.
2. Acceso al repositorio de GitHub (para el workflow de imágenes).
3. Un cliente `mc` de MinIO (o la consola web) para crear el bucket y el usuario.
4. Las credenciales/secretos definidos en [03 — Variables](03-variables-entorno.md).

---

## 2. Imágenes: cómo se construyen y publican

Archivo: `.github/workflows/docker-build.yml`

- Se dispara con `push` a `main`. La ejecución manual (`workflow_dispatch`)
  solo funciona si se elige `main`; una guarda rechaza otras ramas.
- Construye **dos** imágenes para `linux/amd64`:
  - Backend (contexto raíz, `Dockerfile`): Gateway + MS1–MS4.
  - Frontend (contexto `frontend/`, `frontend/Dockerfile`): React + Nginx.
- Publica en GHCR con dos etiquetas: `latest` y `sha-<7 caracteres del commit>`.
- Usa la caché de GitHub Actions para acelerar builds.
- Después publica, el job `deploy-kubero` fija ese `sha-...` en `gateway`,
  `ms1`–`ms4` y `web`, solicita el redeploy y espera a que la salud vuelva a `ok`.
  `minio` no se toca. Requiere el secreto `KUBERO_TOKEN` (ver
  [06 — Runbook](06-runbook-operacion.md#42-desplegar-en-kubero)).

Resultado verificado:

| Imagen | Etiquetas |
| --- | --- |
| `ghcr.io/vncmk78/tallerconnect-backend` | `latest`, `sha-c855bab` |
| `ghcr.io/vncmk78/tallerconnect-frontend` | `latest`, `sha-c855bab` |

> **Flujo vigente (23 de noviembre de 2026):** el workflow está en `main` y
> `on.push.branches` solo incluye `main`. La rama `kubero-deploy` se conserva,
> pero queda fuera del flujo; no hace falta fusionarla para publicar imágenes.
> Su copia del workflow también quedó con `branches: [main]`, así que un push a
> esa rama ya no publica imágenes.

Para publicar una versión nueva:

```bash
git checkout Develop
git merge Vicente          # integrar la tarea terminada
git checkout main
git merge Develop
git push origin main       # dispara Actions → Docker Build
```

> Si las apps de Kubero están en `:latest`, fija `sha-<commit>` antes de este
> push: el tag `latest` se moverá con la nueva imagen. Con el deploy automático,
> el job hará ese cambio por ti al terminar el build.

Esperar el run en **Actions → Docker Build**. El job `deploy-kubero` actualiza
los tags y verifica la salud; si el commit incluye migraciones nuevas, omite el
cambio y deja la instrucción en el resumen del run
(ver [06 — Runbook](06-runbook-operacion.md#4-actualizar-la-versión-desplegada)).

---

## 3. Pipeline y aplicaciones

En el pipeline `tallerconnect` (fase `Production`) existen **7 aplicaciones**:

| App | Tipo | Imagen | Puerto contenedor | Health check |
| --- | --- | --- | --- | --- |
| `gateway` | backend | `ghcr.io/vncmk78/tallerconnect-backend` | 8000 | `/api/health` |
| `ms1` | backend | `ghcr.io/vncmk78/tallerconnect-backend` | 8000 | `/health` |
| `ms2` | backend | `ghcr.io/vncmk78/tallerconnect-backend` | 8000 | `/health` |
| `ms3` | backend | `ghcr.io/vncmk78/tallerconnect-backend` | 8000 | `/health` |
| `ms4` | backend | `ghcr.io/vncmk78/tallerconnect-backend` | 8000 | `/health` |
| `web` | frontend | `ghcr.io/vncmk78/tallerconnect-frontend` | 80 | `/healthz` |
| `minio` | almacenamiento | `elestio/minio:latest` | 9000 | `/minio/health/live` |

Además, en Kubero hay **apps del equipo de Integra IV (app móvil)** que **no
administra Integra II** y que el deploy automático **no modifica**:

| App | Pipeline | Imagen | Dominio | Qué es |
| --- | --- | --- | --- | --- |
| `frontend-movil` | `tallerconnect` | `ghcr.io/victor-agsp/tallerconnect-f…` (tag = commit fijo) | `frontend-movil.inf.uct.cl` | App móvil Expo compilada para web |
| `frontend` | `taller connect-frontend` | `ghcr.io/victor-agsp/tallerconnect-f…` (tag = commit fijo) | `tallerconnect-frontend.inf.uct.cl` | Otra build web de la misma app Expo |

Ambas reenvían `/api/*` de su propio dominio a la Gateway (mismo origen para el
navegador), así que **no necesitan estar en `GATEWAY_CORS_ORIGINS`**. Se
actualizan solo cuando Integra IV cambia su tag en Kubero. Verificación de
integración: [07 — Pruebas realizadas §22](07-pruebas-realizadas.md#22-integración-web-base-de-datos-y-app-móvil-24-11-2026).

### 3.1 Configuración común de las apps backend

- **Imagen:** `ghcr.io/vncmk78/tallerconnect-backend:latest` (o `:sha-c855bab`).
- **Comando:** se deja el del `Dockerfile`
  (`python scripts/iniciar_servicio.py`). No hace falta sobreescribirlo.
- **Variable clave:** `SGTM_SERVICIO` = `gateway` | `ms1` | `ms2` | `ms3` | `ms4`.
- **Puerto del contenedor:** `8000`.
- **Service:** Kubero publica el Service en el puerto **80** con
  `targetPort: http`. Por eso las URLs internas van **sin puerto**.
- **Health check:** el de la tabla anterior.

> El `Dockerfile` arranca Uvicorn con `os.execv`, para que Kubernetes pueda
> enviar `SIGTERM` correctamente al proceso.

### 3.2 Configuración de `web`

- **Imagen:** `ghcr.io/vncmk78/tallerconnect-frontend:latest`.
- **Puerto del contenedor:** `80`.
- **Variable:** `GATEWAY_UPSTREAM=http://gateway-kuberoapp` (sin ruta ni barra
  final). Nginx reenvía `/api/*` conservando el prefijo.
- **Health check:** `/healthz`.
- **Dominio:** `tallerconnect.inf.uct.cl` con TLS.

El `Dockerfile` del frontend compila con `VITE_API_URL=/api`, así que la web
siempre consume su propio origen; no depende de la URL pública de la Gateway ni
de CORS.

### 3.3 Configuración de `minio`

- **Imagen:** `elestio/minio:latest`.
  - Se descartó `minio/minio` porque ya no existe en Docker Hub.
  - Se descartó `quay.io/minio/minio` porque exige autenticación en el pull.
- **Comando:** `server /data --console-address ":9001"`.
- **Variables:** `MINIO_ROOT_USER` y `MINIO_ROOT_PASSWORD` (ver panel).
- **Volumen persistente:** PVC `minio-data-cephfs` con storage class
  **`csi-cephfs-sc`**, montado en `/data`.
  - La storage class `standard` **no existe** en este clúster.
- **Puertos:** 9000 (API S3) y 9001 (consola).
- **Health check:** `/minio/health/live`.
- **Dominio:** `ms4-tallerconnect.inf.uct.cl` con TLS.
  - La raíz responde `307` hacia la consola en el puerto `36553`.
  - El endpoint S3 público es `https://ms4-tallerconnect.inf.uct.cl`.
- **Service interno:** `http://minio-kuberoapp` (puerto 80 → 9000), que es lo que
  usa MS4 como `MS4_S3_ENDPOINT`.

> El dominio `evidencias-tallerconnect.inf.uct.cl` **no existe** en el DNS de la
> UCT y no se pudo crear. Por eso MinIO usa el dominio de MS4 y MS4 pasó a
> `ms4-interno-tallerconnect.inf.uct.cl`.

---

## 4. Addons PostgreSQL

Se creó **un addon por microservicio** (4 en total). Todos con:

- **Tipo:** PostgreSQL.
- **Instance Name:** `postgres` → el Service queda como `<app>-postgres`.
- **Base de datos:** una por servicio (`taller_ms1` … `taller_ms4`).
- **Usuario de la app:** `postgres` con la contraseña definida en el addon.

| App | Host interno | Base | Variable en la app |
| --- | --- | --- | --- |
| `ms1` | `ms1-postgres` | `taller_ms1` | `MS1_DATABASE_URL` |
| `ms2` | `ms2-postgres` | `taller_ms2` | `MS2_DATABASE_URL` |
| `ms3` | `ms3-postgres` | `taller_ms3` | `MS3_DATABASE_URL` |
| `ms4` | `ms4-postgres` | `taller_ms4` | `MS4_DATABASE_URL` |

Formato del DSN:

```text
postgresql+psycopg://postgres:<PASSWORD>@<app>-postgres:5432/<base>
```

> Las bases **no** se exponen a Internet. Solo los pods del pipeline las
> alcanzan por el Service interno.

---

## 5. Dominios

| Dominio | Destino | Uso |
| --- | --- | --- |
| `tallerconnect.inf.uct.cl` | app `web` | Aplicación web |
| `api-tallerconnect.inf.uct.cl` | app `gateway` | API pública para web y móvil |
| `ms1-tallerconnect.inf.uct.cl` | app `ms1` | Diagnóstico directo |
| `ms2-tallerconnect.inf.uct.cl` | app `ms2` | Diagnóstico directo |
| `ms3-tallerconnect.inf.uct.cl` | app `ms3` | Diagnóstico directo |
| `ms4-tallerconnect.inf.uct.cl` | app `minio` | Endpoint S3 público de MinIO |
| `ms4-interno-tallerconnect.inf.uct.cl` | app `ms4` | Diagnóstico directo de MS4 |
| `frontend-movil.inf.uct.cl` | app `frontend-movil` (Integra IV) | App móvil (build web); proxy `/api` → Gateway |
| `tallerconnect-frontend.inf.uct.cl` | app `frontend` (Integra IV) | App móvil (build web); proxy `/api` → Gateway |

Todos con TLS. El único dominio que debe consumir el equipo móvil es
`api-tallerconnect.inf.uct.cl`.

---

## 6. Migraciones de base de datos

Las migraciones **no se ejecutan al iniciar cada pod** (sería peligroso con
réplicas). Se ejecutaron una sola vez con una app temporal.

Procedimiento usado:

1. Crear una app temporal `migraciones` con la imagen del backend.
2. Configurar `SGTM_SERVICIO=migraciones` y **las cuatro** `MSn_DATABASE_URL`.
3. Esperar a que el pod termine. El proceso:
   - espera las bases,
   - ejecuta `alembic upgrade heads` en MS1 → MS4,
   - verifica que las cuatro queden en los heads del código,
   - termina con código de salida.
4. Revisar los logs y **eliminar la app temporal**.

Heads vigentes al momento del despliegue:

| Servicio | Revisión |
| --- | --- |
| MS1 | `0008_contexto_avisos_ms1` |
| MS2 | `0014_nueva_atencion_ms2` |
| MS3 | `0011_avisos_ms3` |
| MS4 | `0001_ms4` |

> Para volver a migrar (por ejemplo, tras un merge con migraciones nuevas),
> repetir el procedimiento. Nunca usar `alembic stamp` sin revisar el estado real.

---

## 7. Datos iniciales

Después de migrar se ejecutó el seed de cuentas de prueba:

```bash
python backend/scripts/seed_usuarios_prueba.py
```

Es **idempotente** (crea o actualiza las cuentas) y requiere
`MS1_DATABASE_URL` y `MS2_DATABASE_URL`, porque crea el usuario en MS1 y su
perfil de cliente en MS2. Resultado y detalle en
[04 — Datos de prueba](04-datos-de-prueba.md).

---

## 8. MinIO: bucket, usuario y política

1. Crear el bucket privado `evidencias`.
2. Crear el usuario `ms4-evidencias` con una contraseña aleatoria.
3. Crear la política `ms4-evidencias-rw` y adjuntarla al usuario.

Política aplicada (solo el bucket `evidencias`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::evidencias"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": ["arn:aws:s3:::evidencias/*"]
    }
  ]
}
```

Comandos usados con `mc`:

```bash
mc alias set tctaller https://ms4-tallerconnect.inf.uct.cl <ROOT_USER> <ROOT_PASSWORD> --api S3v4
mc mb tctaller/evidencias
mc admin user add tctaller ms4-evidencias <PASSWORD>
mc admin policy create tctaller ms4-evidencias-rw politica-ms4-evidencias.json
mc admin policy attach tctaller ms4-evidencias-rw --user ms4-evidencias
mc admin user info tctaller ms4-evidencias
```

Verificación realizada:

- `ms4-evidencias` puede `HeadBucket`, `PutObject`, `GetObject` y `DeleteObject`
  sobre `evidencias`.
- No puede listar otros buckets (`403`).
- Las URLs prefirmadas que genera responden `200`.
- MS4 se autentica en MinIO con `ms4-evidencias` (confirmado con
  `mc admin trace`: `Credential=ms4-evidencias`).

> MS4 **no** usa las credenciales root. Eso reduce el impacto de una filtración.

---

## 9. Orden recomendado para reconstruir todo

1. Crear el pipeline y la fase `Production`.
2. Crear las 4 bases (addons PostgreSQL) con Instance Name `postgres`.
3. Crear las apps `ms1`, `ms2`, `ms3`, `ms4` con la imagen backend y sus
   variables (incluidas las DSN).
4. Crear la app `gateway` con las URLs internas de MS1–MS4 y el CORS del dominio
   web.
5. Crear la app `web` con `GATEWAY_UPSTREAM`.
6. Crear la app `minio` con el PVC y las variables root.
7. Crear el bucket, el usuario y la política de MinIO.
8. Configurar las variables S3 en `ms4`.
9. Ejecutar las migraciones con la app temporal.
10. Ejecutar el seed de cuentas.
11. Configurar los dominios y verificar TLS.
12. Verificar con la matriz de [07 — Pruebas](07-pruebas-realizadas.md).

---

## 10. Comprobaciones rápidas de que el despliegue está sano

```bash
curl -s https://api-tallerconnect.inf.uct.cl/api/health
curl -s https://api-tallerconnect.inf.uct.cl/api/health/servicios
curl -s -o /dev/null -w "%{http_code}\n" https://tallerconnect.inf.uct.cl/
curl -s -o /dev/null -w "%{http_code}\n" https://tallerconnect.inf.uct.cl/healthz
curl -s -o /dev/null -w "%{http_code}\n" https://ms4-tallerconnect.inf.uct.cl/minio/health/live
```

Resultado esperado:

```json
{
  "status": "ok",
  "gateway": "ok",
  "servicios": {
    "ms1_auth": { "estado": "ok" },
    "ms2_taller": { "estado": "ok" },
    "ms3_presupuestos": { "estado": "ok" },
    "ms4_evidencias": { "estado": "ok" }
  }
}
```
