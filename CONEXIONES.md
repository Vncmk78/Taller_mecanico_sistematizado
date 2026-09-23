# Conexiones del Proyecto — Taller Mecánico Sistematizado

Documento de referencia para **todos los pares de integración** (frontend, app
móvil y API). Contiene las URLs de despliegue, credenciales de las bases Neon y
los usuarios de prueba por rol.

> ⚠️ **No subir este archivo a un repositorio público.** Las credenciales son
> de los entornos desplegados. Los datos maestros viven en `.env` (raíz).

---

## 1. Microservicios desplegados

Cada servicio expone su OpenAPI en `{host}/docs`.

| Servicio | Rol del sistema | Puerto dev | Entrypoint |
| --- | --- | --- | --- |
| `ms1_auth` | Autenticación, usuarios y roles | `8001` | `auth_service:app` |
| `ms2_ms_taller` | Órdenes de trabajo (taller) | `8002` | `taller_service:app` |
| `ms3_presupuestos` | Presupuestos (MS3) | `8003` | `presupuestos_service:app` |
| `ms4_evidencias` | Evidencias (MS4) | `8004` | `evidencias_service:app` |

En producción la **Gateway** (`backend/main:app`) enruta:

- `/api` → backend (gateway)
- `/ms1` → ms1_auth
- `/ms2` → ms_taller
- `/ms3` → presupuestos
- `/ms4` → evidencias
- `/(.*)` → frontend React

### URLs de la Gateway desplegada (Vercel)

- Frontend / API base: `https://taller-mecanico-nine-wine.vercel.app`
- Login: `POST https://taller-mecanico-nine-wine.vercel.app/api/auth/login`
- `GET /api/auth/me` (rol del JWT): `https://taller-mecanico-nine-wine.vercel.app/api/auth/me`

Las URLs por servicio se inyectan a la Gateway vía las env vars `GATEWAY_MS1_URL`
… `GATEWAY_MS4_URL` (ver `vercel.json`).

---

## 2. Bases de datos Neon

Todas apuntan a Neon (US East 2), esquema insignia `{base}_owner`. Las URLs
están en `.env` (prefijos `MS1_…MS4_`).

| Servicio | Host (pooler) | Base de datos |
| --- | --- | --- |
| MS1 | `ep-tiny-boat-…pooler.c-7.us-east-2.aws.neon.tech` | `taller_ms1` |
| MS2 | `ep-tiny-boat-…pooler.c-7.us-east-2.aws.neon.tech` | `taller_ms2` |
| MS3 | `ep-tiny-boat-…pooler.c-7.us-east-2.aws.neon.tech` | `taller_ms3` |
| MS4 | `ep-tiny-boat-…pooler.c-7.us-east-2.aws.neon.tech` | `taller_ms4` |

Cadena de conexión (patrón, sustituir credenciales reales de `.env`):

```
postgresql+psycopg://{USUARIO}:{PASSWORD}@{HOST}/{BASE}?sslmode=require&channel_binding=require
```

Variables de entorno por servicio (con prefijo `MS{n}_`):

- `MS{n}_DATABASE_URL` — DSN SQLAlchemy de la base del servicio.
- `MS{n}_JWT_SECRET_KEY` — secreto para firmar/verificar JWTs.
- `GATEWAY_MS{n}_URL` — URL interna de cada servicio (solo en Vercel).

---

## 3. Usuarios de prueba (roles para probar la UI)

Creados y verificados en Neon (`taller_ms1`) con el hash bcrypt del proyecto
y sus roles en `usuario_rol`. El login devuelve un JWT con el rol correcto.

| Rol | Correo | Contraseña |
| --- | --- | --- |
| Cliente | `cliente@pruebas.cl` | `Cliente123!` |
| Mecánico | `mecanico@pruebas.cl` | `Mecanico123!` |
| Administrador | `administrador@pruebas.cl` | `Admin123!` |

Nota: el registro público (`/api/auth/register`) **siempre** asigna el rol
`cliente`. Para roles `mecanico` / `administrador` se insertan directamente en
la BD MS1 (como hicimos en el seed). No hay endpoint público para promover roles.

---

## 4. Comandos útiles

```bash
# Acceder a las bases desde el venv del backend
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head   # MS1 (toma MS1_DATABASE_URL)
```

**Regla de oro:** todos los servicios y el frontend leen sus credenciales desde
`.env` (raíz). Si cambias una URL en Neon, actualiza `.env` y reinicia.
