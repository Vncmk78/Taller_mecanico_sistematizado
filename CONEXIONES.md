# CONEXIONES — Despliegue Vercel + Neon + Usuarios de prueba

Documento de conexión del SGTM desplegado en **Vercel** con base de datos
**Neon** (PostgreSQL serverless) y los cuatro microservicios tras un API
Gateway. Este documento es la fuente de verdad para el equipo: define los
endpoints públicos, las variables de entorno, los usuarios de prueba y los
pasos de despliegue.

## Base del despliegue en producción

```
https://tallerconect.vercel.app
```

---

## 1. Arquitectura desplegada

```
https://tallerconect.vercel.app/
├── /            → Frontend Web (React + Vite)     [servicio Vercel: frontend]
├── /api/*       → API Gateway (FastAPI)           [servicio Vercel: backend]
│                  └── proxya a MS1..MS4 según el primer segmento:
│                      /api/auth/*         → ms1 (auth)
│                      /api/vehiculos/*    → ms2 (taller)
│                      /api/ordenes/*      → ms2
│                      /api/orden/*        → ms2
│                      /api/clientes/*     → ms2
│                      /api/mecanicos/*    → ms2
│                      /api/presupuestos/* → ms3
│                      /api/presupuesto/*  → ms3
│                      /api/repuestos/*    → ms3
│                      /api/proveedores/*  → ms3
│                      /api/inventario/*   → ms3
│                      /api/evidencias/*   → ms4
│                      /api/evidencia/*    → ms4
├── /ms1/docs     → Swagger de MS1 (acceso directo al servicio)
├── /ms2/docs     → Swagger de MS2
├── /ms3/docs     → Swagger de MS3
├── /ms4/docs     → Swagger de MS4
└── /docs         → Swagger de la Gateway
```

Definición de servicios en `vercel.json` (modelo Vercel Services). Los
entrypoints usan **notación de módulo con puntos** (relativa al root del
servicio), y cada MS limpia su prefijo con `rewrites` internos al servicio:

| Servicio | Root | Entrypoint | URL pública |
| --- | --- | --- | --- |
| `frontend` | `frontend` | — (Vite) | `/` |
| `backend` (Gateway) | `backend` | `gateway.main:app` | `/api/*`, `/docs` |
| `ms-auth` | `backend` | `services.ms1_auth.main:app` | `/ms1/*` |
| `ms-taller` | `backend` | `services.ms2_taller.main:app` | `/ms2/*` |
| `ms-presupuestos` | `backend` | `services.ms3_presupuestos.main:app` | `/ms3/*` |
| `ms-evidencias` | `backend` | `services.ms4_evidencias.main:app` | `/ms4/*` |

La gateway enlaza los microservicios con **bindings de servicio**:
`GATEWAY_MS1_URL` … `GATEWAY_MS4_URL` (los resuelve Vercel al desplegar, no se
escriben a mano).

---

## 2. Endpoints públicos

### 2.1 Gateway (todo el mundo pasa por acá)

Base: `https://tallerconect.vercel.app`

| Método | Ruta | Descripción | Auth |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Estado de la Gateway | — |
| `POST` | `/api/auth/register` | Registro público (rol Cliente) | — |
| `POST` | `/api/auth/login` | Login → JWT + usuario con roles | — |
| `GET` | `/api/auth/me` | Usuario autenticado | Bearer |
| `GET` | `/api/vehiculos` | Cliente lista los suyos; Administrador lista todos | Bearer |
| `GET` | `/api/vehiculos/asignados` | Vehículos con órdenes asignadas al Mecánico | Bearer |
| `GET` | `/api/vehiculos/{id}` | Detalle según rol (propios, todos o asignados) | Bearer |
| `POST` | `/api/vehiculos` | Registra un vehículo (rol Cliente) | Bearer |
| `PATCH` | `/api/vehiculos/{id}` | Actualiza un vehículo propio (rol Cliente) | Bearer |
| `POST` | `/api/ordenes` | Crea una orden (rol Administrador) | Bearer |
| `GET` | `/api/ordenes` | Lista órdenes visibles | Bearer |
| `GET` | `/api/ordenes/{id}` | Detalle de una orden visible | Bearer |
| `PUT` | `/api/ordenes/{id}/mecanico` | Asigna o reasigna el mecánico responsable | Bearer |
| `GET` | `/api/ordenes/{id}/historial` | Historial de estados de una orden | Bearer |
| `PATCH` | `/api/ordenes/{id}/estado` | Cambia el estado de una orden | Bearer |

> Regla del gateway: llama siempre por **primer segmento**. Endpoints de
> negocio que aún no existan en un MS devolverán `404 {"detail":"Not Found"}`
> (los agregan los integrantes responsables de cada MS).

> Respuestas de vehículo: `GET /api/vehiculos*` y `POST/PATCH /api/vehiculos`
> incluyen `cliente_id` (perfil Cliente de MS2) junto a `vehiculo_id`, `patente`,
> `marca`, `modelo`, `anio` y `kilometraje`. MS2 no resuelve datos de MS1, así
> que el contrato entrega identificadores y no nombres: quien consuma la API
> muestra `Cliente #<cliente_id>` en lugar de inventar un propietario. Lo mismo
> aplica al mecánico de una orden, que solo trae `mecanico_actual_id`.

### 2.2 Acceso directo a cada microservicio

| URL | Descripción |
| --- | --- |
| `https://tallerconect.vercel.app/ms1/docs` | Swagger MS1 (auth) |
| `https://tallerconect.vercel.app/ms1/health` | Health MS1 |
| `https://tallerconect.vercel.app/ms2/docs` | Swagger MS2 (vehículos, órdenes) |
| `https://tallerconect.vercel.app/ms2/health` | Health MS2 |
| `https://tallerconect.vercel.app/ms2/health/db` | Health MS2 + conexión Neon |
| `https://tallerconect.vercel.app/ms3/docs` | Swagger MS3 (presupuestos, repuestos) |
| `https://tallerconect.vercel.app/ms3/health` | Health MS3 |
| `https://tallerconect.vercel.app/ms3/health/db` | Health MS3 + conexión Neon |
| `https://tallerconect.vercel.app/ms4/docs` | Swagger MS4 (evidencias) |
| `https://tallerconect.vercel.app/ms4/health` | Health MS4 |
| `https://tallerconect.vercel.app/docs` | Swagger de la Gateway |

> Para la **app móvil** usar siempre `https://tallerconect.vercel.app/api/*`:
> el consumo es idéntico al frontend web.

---

## 3. Usuarios de prueba (web y móvil)

Usuarios sembrados con `backend/scripts/seed_usuarios_prueba.py` (idempotente).
Ya están creados en Neon.

| Rol | Correo | Contraseña |
| --- | --- | --- |
| **Cliente** | `cliente@pruebas.cl` | `ClientePrueba123!` |
| **Mecánico** | `mecanico@pruebas.cl` | `MecanicoPrueba123!` |
| **Administrador** | `administrador@pruebas.cl` | `AdminPrueba123!` |

- El usuario **Cliente** tiene perfil creado en MS2 (para usar `/api/vehiculos/mios`).
- Los roles provienen de la migración `0002_roles_iniciales_ms1`
  (`cliente`, `mecanico`, `administrador`).

### Login de ejemplo (curl)

```bash
curl -X POST https://tallerconect.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"cliente@pruebas.cl","password":"ClientePrueba123!"}'
```

Respuesta: `access_token` (JWT) + datos del usuario con sus roles. Usar el
token como `Authorization: Bearer <token>` en los endpoints protegidos.

---

## 4. Base de datos Neon

Cuatro bases independientes, una por microservicio (§8 aislamiento de datos):

| Servicio | Variable | Base Neon |
| --- | --- | --- |
| MS1 (auth) | `MS1_DATABASE_URL` | `taller_ms1` |
| MS2 (taller) | `MS2_DATABASE_URL` | `taller_ms2` |
| MS3 (presupuestos) | `MS3_DATABASE_URL` | `taller_ms3` |
| MS4 (evidencias) | `MS4_DATABASE_URL` | `taller_ms4` |

Formato del DSN Neon (con SSL obligatorio):

```
postgresql+psycopg://USUARIO:PASSWORD@HOST/taller_ms1?sslmode=require
```

### Migraciones contra Neon

Con `backend/.env` apuntando a Neon (los servicios leen `MSn_DATABASE_URL`):

```powershell
cd backend
.\scripts\migrar_neon.ps1
```

Aplica las migraciones de MS1, MS2 y MS3 (`alembic upgrade head`). MS4 todavía
no tiene migraciones (no hay modelos). El seed DEBE ejecutarse después:

```powershell
python scripts/seed_usuarios_prueba.py
```

> Estado actual de la BD en producción: **migraciones MS1/MS2/MS3 aplicadas** y
> **seed ejecutado** (clientes de prueba ya creados).

---

## 5. Variables de entorno en Vercel

En el proyecto de Vercel, configurar como Environment Variables (Production):

| Variable | Valor |
| --- | --- |
| `MS1_DATABASE_URL` | DSN Neon base `taller_ms1` con `?sslmode=require` |
| `MS2_DATABASE_URL` | DSN Neon base `taller_ms2` con `?sslmode=require` |
| `MS3_DATABASE_URL` | DSN Neon base `taller_ms3` con `?sslmode=require` |
| `MS4_DATABASE_URL` | DSN Neon base `taller_ms4` con `?sslmode=require` |
| `MS1_JWT_SECRET_KEY` | Clave aleatoria ≥ 32 caracteres (HS256, compartida con MS2) |
| `MS2_JWT_SECRET_KEY` | La MISMA clave que `MS1_JWT_SECRET_KEY` |
| `MS1_JWT_ALGORITHM` | `HS256` |
| `MS2_JWT_ALGORITHM` | `HS256` |
| `GATEWAY_CORS_ORIGINS` | `https://tallerconect.vercel.app` (lista CSV, opcional) |

> `GATEWAY_MS1_URL`…`GATEWAY_MS4_URL` **no se escriben a mano**: las crea Vercel
> automáticamente con los bindings de servicio definidos en `vercel.json`.
> El campo `CORS_ORIGINS` de la gateway tolera CSV y JSON (no revienta el
> arranque si llega como `a.com,b.com`).

Generar clave JWT:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 6. Pasos de despliegue (Vercel)

1. Hacer merge de la rama de trabajo (`Gustavo`) a `Develop` y luego a `main`.
2. En Vercel: **Add New → Project**, importar el repo desde la rama `main`.
3. Vercel detecta el `vercel.json` con los servicios. No es necesario build
   command manual (Vite y FastAPI se detectan por framework).
4. Agregar las variables de entorno de la Sección 5.
5. Deploy. Vercel crea los servicios `frontend`, `backend`, `ms-auth`,
   `ms-taller`, `ms-presupuestos`, `ms-evidencias` y los bindings internos.
6. Configurar Neon (Sección 4) y ejecutar migraciones + seed.
7. Verificar:
   - `GET https://tallerconect.vercel.app/api/health` → `{"status":"ok"}`
   - `POST https://tallerconect.vercel.app/api/auth/login` con
     `cliente@pruebas.cl` → token JWT.
   - `https://tallerconect.vercel.app/ms1/docs` carga Swagger MS1.
   - Abrir `https://tallerconect.vercel.app/` → Login del frontend funciona
     (usa `/api` relativo).

### Despliegue local (desarrollo)

```powershell
# Backend (usa un .env local con DSNs locales)
cd backend
uvicorn gateway.main:app --reload --port 8000
# Microservicios por separado (para desarrollo)
uvicorn services.ms1_auth.main:app --reload --port 8001
uvicorn services.ms2_taller.main:app --reload --port 8002
uvicorn services.ms3_presupuestos.main:app --reload --port 8003
uvicorn services.ms4_evidencias.main:app --reload --port 8004

# Frontend (el proxy de Vite reenvía /api → localhost:8000)
cd frontend
npm run dev
```

---

## 7. Notas técnicas

- **CORS**: la Gateway expone `Access-Control-Allow-Origin`. En Vercel el
  frontend y la API comparten origen, pero la app móvil o previews
  `*.vercel.app` quedan cubiertos por `allow_origin_regex`.
- **Paths relativos**: el frontend usa `baseURL '/api'`; en producción se
  resuelve contra el mismo dominio. `VITE_API_URL` queda disponible para
  sobreescribir (ej. `https://tallerconect.vercel.app/api`).
- **JWT**: HS256 compartido entre MS1 (genera) y MS2 (valida). Nunca subir los
  secrets al repositorio.
- **Entrypoints**: usar notación de módulo con puntos (`gateway.main:app`,
  `services.ms1_auth.main:app`) relativa al root del servicio, y `rewrites`
  internos del servicio para limpiar los prefijos `/msN`. No usar `routes` +
  `transforms` para esto en FastAPI (deja el path original).
- Archivos relacionados: `vercel.json` (servicios), `backend/.env.example`
  (plantilla de variables), `backend/scripts/migrar_neon.ps1`,
  `backend/scripts/seed_usuarios_prueba.py`.

---

## 8. Última verificación de producción (2026-09-24)

Resultados probados contra `https://tallerconect.vercel.app`:

| Prueba | Resultado |
| --- | --- |
| `GET /api/health` | 200 `{"status":"ok","servicio":"gateway"}` |
| `GET /` (frontend) | 200 |
| `GET /ms1/docs` … `/ms4/docs` | 200 (los 4 Swagger cargan) |
| `GET /ms1/health` + `/ms2/health` + `/ms3/health` + `/ms4/health` | 200 |
| `GET /ms2/health/db` + `/ms3/health/db` | 200 (`database:"ok"`) |
| `POST /api/auth/login` (cliente, mecánico, admin) | 200 + JWT |
| `POST /api/auth/login` (contraseña incorrecta) | 401 |
| `GET /api/auth/me` (con token) | 200 usuario con roles |
| `GET /api/vehiculos` (token cliente) | 200 `[]` |
| `GET /api/vehiculos` (token admin) | 200 (el Administrador ya ve todos los vehículos; antes respondía 403) |

---

## 9. Verificación de pruebas funcionales de los primeros flujos web (2026-09-30)

Pruebas automatizadas (robots) ejecutadas tras sincronizar `Vicente` con el
`main` actual (FF a `6690a87`, que incluye el trabajo del gateway de Basti):

| Suite | Comando | Resultado |
| --- | --- | --- |
| Backend | `.\\.venv\\Scripts\\python.exe -m pytest -q` (desde `backend/`) | 427 passed, 61 skipped (saltan JWT/PostgreSQL) |
| Lint frontend | `npm run lint` | 0 warnings / 0 errors |
| Tests frontend | `npm test` | 209 passed / 43 archivos |
| Build frontend | `npm run build` (tsc -b && vite build) | OK |

Flujos cubiertos: auth (register/login/me), vehículos (listado por rol,
`/api/vehiculos/asignados`, detalle, alta, PATCH) y órdenes (listado, filtro,
paginación, detalle, historial, `PATCH .../estado` con 409/422/403/404/401,
asignación de mecánico). Ver plan detallado en
`.opencode/plans/r32x-pruebas-funcionales-primeros-flujos-web.md`.

Ajustes post-merge: los dos tests de `test_gateway_openapi_ejemplos.py` de Basti
asumían 11 operaciones de negocio; pasan a validar las **14 operaciones**
vigentes (set explícito) y se agregó el ejemplo 200 `lista_asignados` de
`GET /api/vehiculos/asignados` en `gateway/openapi_ejemplos.py`. Dependencia
nueva del venv: `openapi-spec-validator` (de `requirements-dev.txt`).

## 10. Reemplazo de datos simulados por respuestas reales de la Gateway (2026-09-30)

Las 14 operaciones de negocio existen y el frontend ya las consumía; lo que
quedaba eran datos de demostración en producción (seeds de stores, nombres de
dueño/mecánico y filtros por identidades de ejemplo). Ahora ninguna vista depende
de datos simulados.

| Suite | Comando | Resultado |
| --- | --- | --- |
| Backend | `.\\.venv\\Scripts\\python.exe -m pytest -q` (desde `backend/`) | 427 passed, 61 skipped |
| Lint frontend | `npm run lint` | 0 warnings / 0 errors (139 archivos) |
| Tests frontend | `npm test` | 210 passed / 43 archivos |
| Build frontend | `npm run build` (tsc -b && vite build) | OK |

**Backend**: `VehiculoRespuesta` expone ahora `cliente_id` (schema de MS2,
contrato de la Gateway y ejemplos del OpenAPI), que es el dato que la interfaz
muestra como propietario real.

**Frontend**:
- Los 3 stores (`useVehicleStore`, `useOrderStore`, `useOrderHistoryStore`)
  arrancan vacíos: la caché solo contiene respuestas de la Gateway.
- `VehicleService` mapea `cliente_id` a `Vehicle.clientId`. En el portal Cliente
  manda el `id` de la sesión (`usuario_id` de MS1) para resolver pertenencia;
  en Administrador y Mecánico queda el `cliente_id` real de MS2.
- Se retiraron `CURRENT_CLIENT_ID`, `CURRENT_MECHANIC_ID`, `mockOwners`,
  `mockMechanics` y `mockAssignedVehicleIds` de producción, junto con el archivo
  `infrastructure/mocks/orders.mock.ts`. Los mocks que quedan son fixtures
  exclusivos de los tests.
- Los filtros offline por identidad se eliminaron: la Gateway ya devuelve solo
  lo que corresponde al rol, así que la caché se muestra tal cual. El alcance de
  un vehículo para el rol Mecánico lo aplica el backend (404 si no está
  asignado).
- `VehicleInfoPanel` recibe `ownerLabel` (p. ej. `Cliente #7`) en vez de un
  objeto con nombre, correo y teléfono simulados; las órdenes muestran
  `Mecánico <id>` o `Sin asignar`.

Pendiente de coordinar con backend: exponer nombres reales requiere que MS2
resuelva MS1 (o un endpoint de clientes/mecánicos), fuera del alcance de esta
misión. Ver `frontend/docs/contratos-openapi.md` y el plan en
`.opencode/plans/r32x-reemplazar-mocks-gateway.md`.