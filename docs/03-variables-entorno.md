# 03 — Variables de entorno por aplicación

Todas las variables se configuran en el **panel de Kubero**, dentro de cada app.
No se usa ningún archivo `.env` en el clúster y **nunca** se sube un `.env` al
repositorio.

Convenciones:

- `<SECRETO>` = valor real guardado en el panel; no se documenta aquí porque el
  repositorio es público.
- Las URLs internas van **sin puerto**: el Service de Kubero escucha en 80 y
  apunta al puerto `http` del contenedor.
- No configures `PORT`: el contenedor usa 8000 por defecto y el Service lo
  traduce a 80.

---

## 1. Resumen de secretos

Estos valores **no** están en el repositorio. Se obtienen del responsable del
despliegue y se guardan en un gestor de contraseñas.

| Secreto | Dónde se usa | Debe coincidir en |
| --- | --- | --- |
| JWT compartido | `MSn_JWT_SECRET_KEY` | MS1, MS2, MS3, MS4 |
| Secreto de eventos de orden | `MS1_EVENT_SHARED_SECRET` / `MS2_EVENT_SHARED_SECRET` | MS1 y MS2 |
| Secreto de avisos MS3 | `MS1_MS3_EVENT_SHARED_SECRET` / `MS3_EVENT_SHARED_SECRET` | MS1 y MS3 |
| Secreto de consulta de destinatario | `MS1_MS2_NOTIFICATION_SECRET` / `MS2_NOTIFICATION_LOOKUP_SECRET` | MS1 y MS2 |
| Contraseña de cada PostgreSQL | `MSn_DATABASE_URL` | Cada app con su addon |
| Credenciales root de MinIO | `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Solo app `minio` |
| Credenciales de MS4 en MinIO | `MS4_S3_ACCESS_KEY` / `MS4_S3_SECRET_KEY` | Solo app `ms4` |

Recomendaciones:

- Cada secreto debe tener **al menos 32 caracteres** (el JWT y los secretos de
  servicio lo exigen al arrancar).
- No reutilices el JWT como secreto de servicio.
- Si rotas un secreto, cámbialo en **todas** las apps que lo comparten y
  reinícialas.

---

## 2. `gateway`

| Variable | Valor | Notas |
| --- | --- | --- |
| `SGTM_SERVICIO` | `gateway` | Obligatoria |
| `GATEWAY_MS1_URL` | `http://ms1-kuberoapp` | Sin puerto |
| `GATEWAY_MS2_URL` | `http://ms2-kuberoapp` | Sin puerto |
| `GATEWAY_MS3_URL` | `http://ms3-kuberoapp` | Sin puerto |
| `GATEWAY_MS4_URL` | `http://ms4-kuberoapp` | Sin puerto |
| `GATEWAY_CORS_ORIGINS` | `https://tallerconnect.inf.uct.cl` | Solo el dominio web |
| `GATEWAY_CORS_ALLOW_CREDENTIALS` | `true` | |
| `GATEWAY_CORS_ORIGIN_REGEX` | *(vacío)* | No se autorizan previews |
| `GATEWAY_TIMEOUT_CONNECT_SECONDS` | `3.0` | Opcional (valor por defecto) |
| `GATEWAY_TIMEOUT_READ_SECONDS` | `15.0` | Opcional |
| `GATEWAY_TIMEOUT_WRITE_SECONDS` | `15.0` | Opcional |
| `GATEWAY_TIMEOUT_POOL_SECONDS` | `5.0` | Opcional |
| `GATEWAY_TIMEOUT_ARCHIVOS_SECONDS` | `60.0` | Subidas de evidencia |
| `GATEWAY_MAX_BODY_BYTES` | `1048576` | 1 MiB para JSON |
| `GATEWAY_MAX_BODY_ARCHIVOS_BYTES` | `12582912` | 12 MiB para evidencias |
| `GATEWAY_HEALTH_TIMEOUT_SECONDS` | `2.0` | Health de servicios |

> La Gateway **no** recibe el JWT compartido ni las DSN. Solo enruta.

---

## 3. `ms1` — Autenticación y usuarios

| Variable | Valor | Notas |
| --- | --- | --- |
| `SGTM_SERVICIO` | `ms1` | Obligatoria |
| `MS1_DATABASE_URL` | `postgresql+psycopg://postgres:<SECRETO>@ms1-postgres:5432/taller_ms1` | |
| `MS1_JWT_SECRET_KEY` | `<SECRETO>` | Mismo en MS1–MS4 |
| `MS1_JWT_ALGORITHM` | `HS256` | |
| `MS1_JWT_EXPIRE_MINUTES` | `60` | |
| `MS1_LOGIN_MAX_INTENTOS` | `5` | Bloqueo tras intentos fallidos |
| `MS1_LOGIN_BLOQUEO_MINUTOS` | `15` | |
| `MS1_EVENT_SHARED_SECRET` | `<SECRETO>` | Igual que en MS2 |
| `MS1_MS3_EVENT_SHARED_SECRET` | `<SECRETO>` | Igual que en MS3 |
| `MS1_MS2_URL` | `http://ms2-kuberoapp` | Para resolver destinatarios |
| `MS1_MS2_NOTIFICATION_SECRET` | `<SECRETO>` | Igual que en MS2 |
| `MS1_NOTIFICATION_WORKER_ENABLED` | `false` | **Correo desactivado** (no hay SMTP) |

> Si en el futuro se habilita correo, agregar `MS1_SMTP_HOST`, `MS1_SMTP_PORT`,
> `MS1_SMTP_USUARIO`, `MS1_SMTP_CLAVE`, `MS1_SMTP_REMITENTE`, `MS1_SMTP_MODO` y
> poner `MS1_NOTIFICATION_WORKER_ENABLED=true`.

---

## 4. `ms2` — Vehículos y órdenes

| Variable | Valor | Notas |
| --- | --- | --- |
| `SGTM_SERVICIO` | `ms2` | Obligatoria |
| `MS2_DATABASE_URL` | `postgresql+psycopg://postgres:<SECRETO>@ms2-postgres:5432/taller_ms2` | |
| `MS2_JWT_SECRET_KEY` | `<SECRETO>` | Mismo en MS1–MS4 |
| `MS2_JWT_ALGORITHM` | `HS256` | |
| `MS2_EVENT_SHARED_SECRET` | `<SECRETO>` | Igual que en MS1 |
| `MS2_EVENT_WORKER_ENABLED` | `true` | Publica cambios de estado |
| `MS2_EVENT_POLL_SECONDS` | `1.0` | Opcional |
| `MS2_EVENT_TIMEOUT_SECONDS` | `5.0` | Opcional |
| `MS2_EVENT_RETRY_MAX_SECONDS` | `300` | Opcional |
| `MS2_MS1_URL` | `http://ms1-kuberoapp` | Sin puerto |
| `MS2_MS1_TIMEOUT_SEGUNDOS` | `3.0` | Validación de asignaciones |
| `MS2_MS3_URL` | `http://ms3-kuberoapp` | Reservas y disponibilidad |
| `MS2_TIMEZONE` | `America/Santiago` | |
| `MS2_NOTIFICATION_LOOKUP_SECRET` | `<SECRETO>` | Igual que en MS1 |

---

## 5. `ms3` — Presupuestos, repuestos y proveedores

| Variable | Valor | Notas |
| --- | --- | --- |
| `SGTM_SERVICIO` | `ms3` | Obligatoria |
| `MS3_DATABASE_URL` | `postgresql+psycopg://postgres:<SECRETO>@ms3-postgres:5432/taller_ms3` | |
| `MS3_JWT_SECRET_KEY` | `<SECRETO>` | Mismo en MS1–MS4 |
| `MS3_JWT_ALGORITHM` | `HS256` | |
| `MS3_MS2_URL` | `http://ms2-kuberoapp` | Visibilidad de órdenes |
| `MS3_MS2_TIMEOUT_SEGUNDOS` | `3` | Opcional |
| `MS3_MS1_URL` | `http://ms1-kuberoapp` | Publicación de avisos |
| `MS3_EVENT_SHARED_SECRET` | `<SECRETO>` | Igual que en MS1 |
| `MS3_EVENT_WORKER_ENABLED` | `true` | **Sin esto no salen los avisos** |
| `MS3_EVENT_POLL_SECONDS` | `2` | Opcional |
| `MS3_EVENT_TIMEOUT_SECONDS` | `10` | Opcional |

> El error más común es configurar `MS3_EVENT_SHARED_SECRET` pero olvidar
> `MS3_EVENT_WORKER_ENABLED=true`. En ese caso la alerta se guarda en la outbox
> de MS3 pero nunca llega a MS1.

---

## 6. `ms4` — Evidencia multimedia

| Variable | Valor | Notas |
| --- | --- | --- |
| `SGTM_SERVICIO` | `ms4` | Obligatoria |
| `MS4_DATABASE_URL` | `postgresql+psycopg://postgres:<SECRETO>@ms4-postgres:5432/taller_ms4` | |
| `MS4_JWT_SECRET_KEY` | `<SECRETO>` | Mismo en MS1–MS4 |
| `MS4_JWT_ALGORITHM` | `HS256` | |
| `MS4_MS2_URL` | `http://ms2-kuberoapp` | Visibilidad de órdenes |
| `MS4_MS2_TIMEOUT_SEGUNDOS` | `3` | Opcional |
| `MS4_MS3_URL` | `http://ms3-kuberoapp` | Presupuesto de la orden |
| `MS4_MS3_TIMEOUT_SEGUNDOS` | `3` | Opcional |
| `MS4_S3_ENDPOINT` | `http://minio-kuberoapp` | Endpoint **interno** |
| `MS4_S3_ACCESS_KEY` | `ms4-evidencias` | Usuario limitado |
| `MS4_S3_SECRET_KEY` | `<SECRETO>` | |
| `MS4_S3_BUCKET` | `evidencias` | |
| `MS4_S3_REGION` | `us-east-1` | |
| `MS4_S3_SECURE` | `false` | Interno HTTP |
| `MS4_S3_PUBLIC_ENDPOINT` | `https://ms4-tallerconnect.inf.uct.cl` | Para firmar descargas |
| `MS4_URL_DESCARGA_TTL_SECONDS` | `300` | 5 minutos |
| `MS4_TIPOS_PERMITIDOS` | `["image/jpeg","image/png","image/webp","video/mp4","video/quicktime"]` | Opcional (valor por defecto) |
| `MS4_MAX_BYTES_FOTO` | `10485760` | 10 MiB |
| `MS4_MAX_BYTES_VIDEO` | `104857600` | 100 MiB |

> `MS4_S3_ENDPOINT` debe ser el nombre **interno** (`minio-kuberoapp`) y
> `MS4_S3_PUBLIC_ENDPOINT` el dominio **público**. Si ambos son internos, las
> URLs prefirmadas no funcionan fuera del clúster. Si ambos son públicos, MS4
> sale a Internet innecesariamente.

---

## 7. `web`

| Variable | Valor | Notas |
| --- | --- | --- |
| `GATEWAY_UPSTREAM` | `http://gateway-kuberoapp` | Sin ruta ni barra final |

El build ya viene con `VITE_API_URL=/api`. No se configuran credenciales en el
frontend.

---

## 8. `minio`

| Variable | Valor | Notas |
| --- | --- | --- |
| `MINIO_ROOT_USER` | `<SECRETO>` | Solo administración |
| `MINIO_ROOT_PASSWORD` | `<SECRETO>` | Solo administración |

Comando del contenedor:

```text
server /data --console-address ":9001"
```

Volumen: PVC `minio-data-cephfs` (storage class `csi-cephfs-sc`) montado en
`/data`.

---

## 9. Variables de desarrollo local (referencia)

El archivo `backend/.env.example` documenta todas las variables con valores de
ejemplo para desarrollo. Los `localhost` de esa plantilla **no sirven en
Kubernetes**: dentro de un pod, `localhost` es el propio pod, no otro servicio.

Para desarrollo local:

- PostgreSQL en `localhost:5433`–`5436`.
- MinIO en `localhost:9000`.
- Gateway en `localhost:8000`.
- Frontend en `localhost:5173`.

Ver `backend/README.md` y `frontend/README.md`.
