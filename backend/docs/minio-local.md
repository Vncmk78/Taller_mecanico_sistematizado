# MinIO local para MS4 (Evidencia Multimedia)

MinIO es el almacenamiento de objetos **S3-compatible** donde MS4 guarda las
fotos y videos de evidencia (los metadatos van en su PostgreSQL). Esta guía
explica cómo levantarlo en desarrollo.

El contenedor del servidor usa la imagen de **Chainguard**
(`cgr.dev/chainguard/minio`, fijada por digest), parcheada y sin
vulnerabilidades conocidas, porque MinIO retiró sus imágenes de la edición
comunitaria de **Docker Hub** (tanto `minio/minio` como `minio/mc`). Para el
contenedor de inicialización se usa el cliente oficial `quay.io/minio/mc`
(el cliente no expone el servidor, y quay.io es el registro oficial de MinIO),
fijado a la versión exacta `RELEASE.2025-08-13T08-35-41Z`.

## Requisitos

- Docker Desktop en ejecución.
- Copiar `.env.example` a `.env` (si aún no existe) y ajustar credenciales.

## Levantar

```bash
cd backend
docker compose up -d minio minio_init
```

Esto:

1. levanta `sgtm_minio` (API S3 en `localhost:9000`, consola web en
   `localhost:9001`);
2. espera a que esté sano (healthcheck con `mc ready`, porque la imagen de
   Chainguard no trae `curl` ni `wget`);
3. `sgtm_minio_init` se ejecuta una sola vez y:
   - crea el bucket `evidencias` si no existe;
   - lo deja **privado** (sin acceso anónimo);
   - crea el usuario de MS4 (`MS4_S3_ACCESS_KEY`);
   - le aplica la política `politica-ms4` (`minio/politica-ms4.json`), con
     permisos `get`/`put`/`delete` solo sobre el bucket `evidencias`.

El init es **idempotente**: si se vuelve a correr `docker compose up`,
los pasos que ya existen simplemente se omiten sin marcar error.

Verificar el estado:

```bash
docker compose ps
```

- `sgtm_minio` debe estar `healthy`.
- `sgtm_minio_init` debe estar `exited 0` (terminó bien).

## Consola web

Abrir <http://localhost:9001> y entrar con `MINIO_ROOT_USER`/
`MINIO_ROOT_PASSWORD` del `.env`. Ahí se ve el bucket `evidencias` y el
usuario `ms4-evidencias` con su política.

> El root `admin-local` es solo para administrar MinIO. MS4 nunca lo usa;
> opera con el usuario `ms4-evidencias` de mínimo privilegio.

## Credenciales que usa MS4

Las variables (en `.env`, con prefijo `MS4_`) que MS4 lee para el cliente S3:

| Variable | Por defecto | Sentido |
|---|---|---|
| `MS4_S3_ENDPOINT` | `http://localhost:9000` | URL del almacenamiento |
| `MS4_S3_ACCESS_KEY` | `ms4-evidencias` | Usuario de MS4 en MinIO |
| `MS4_S3_SECRET_KEY` | `cambia-esta-clave-ms4` | Clave del usuario de MS4 |
| `MS4_S3_BUCKET` | `evidencias` | Bucket privado |
| `MS4_S3_REGION` | `us-east-1` | Región del cliente |
| `MS4_S3_SECURE` | `false` | `true` si el endpoint usa HTTPS |

Los valores por defecto coinciden con los de `minio_init`, así que un `.env`
recién copiado funciona sin cambios.

## Verificación manual (checklist de seguridad)

1. **Bucket privado (control 2.1).** Un `GET` anónimo debe responder `403`:

   ```bash
   curl -i http://localhost:9000/evidencias/ | findstr /i "403"
   ```

2. **Permisos mínimos (control 2.3).** Entrar a la consola como
   `ms4-evidencias` (usuario MS4) y comprobar que **no** puede crear otro
   bucket. Puede listar y operar objetos solo dentro de `evidencias`.

3. **Credenciales fuera del repo (control 2.2).** El repo solo contiene
   `.env.example` con valores de ejemplo. Comprobar que las claves reales no
   están versionadas:

   ```bash
   git grep -n "cambia-esta-clave" backend 2>$null; git status --short backend/.env
   ```

## Apagar

```bash
docker compose down            # conserva los datos
docker compose down -v         # borra también los datos de MinIO y las bases
```