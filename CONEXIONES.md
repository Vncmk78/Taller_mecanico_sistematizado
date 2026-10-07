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
| Backend | `.\.venv\Scripts\python.exe -m pytest -q` (desde `backend/`) | 427 passed, 61 skipped |
| Lint frontend | `npm run lint` | 0 warnings / 0 errors (150 archivos) |
| Tests frontend | `npm test` | 286 passed / 51 archivos |
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

## Estados de carga, vacío y error en la interfaz

Los 3 portales (Administrador, Mecánico y Cliente) comparten los mismos estados en
los listados, detalles e historial de vehículos y órdenes, con el texto
acomodado a cada portal.

**`isOffline` ya no significa "cualquier error"**: `isOfflineError`
(`frontend/src/infrastructure/api/errors.ts`) solo marca `true` cuando el fallo
es de transporte —error no Axios, Axios sin `response`, o `502/503/504`—. Un
`500` u otro `5xx` con respuesta llega como error del servidor, porque el
problema no es la conexión del usuario. Un `404` en un detalle se traduce a
"no encontrado" en vez de a un error.

| Estado | Comportamiento |
| --- | --- |
| Cargando | `LoadingState` o skeleton según la vista |
| Vacío | `EmptyState` con el texto del portal y, si aplica, la acción para crear el primer registro |
| Sin conexión | `OfflineBanner` + los últimos datos de la caché, con `RetryButton` |
| Error del servidor con caché | Se conservan los datos y se avisa en un `Alert` con reintento |
| Error del servidor sin caché | `ErrorState` a pantalla completa con mensaje y botón de reintento |
| Detalle inexistente | `EmptyState` "no encontrado" con el link de regreso del portal |

Detalles del comportamiento:

- `fetchCollection` limpia `status`, `error` e `isOffline` al iniciar cada
  intento, para que un reintento no herede el error anterior.
- Ante un fallo nunca se borra la caché: primero se avisa, después se muestran
  los últimos datos conocidos.
- Un detalle distingue `notFound` (el `404` real) de `failed` (el fetch falló sin
  copia local), de modo que un error de red no se presenta como "no encontrado".
- El historial de la orden usa su propio aviso: "No fue posible mostrar el
  historial de estados de esta orden." en vez del vacío "Aún no hay registros".
- Componentes nuevos reutilizables: `EmptyState`, `ErrorState` y `RetryButton`;
  `OfflineBanner` quedó delegando el reintento en `RetryButton`.

La tabla completa por código de respuesta está en
`frontend/docs/contratos-openapi.md`, sección "Estados de carga, vacío y error".

## Mapeo y errores probados con payloads reales del backend (2026-09-30)

Los tests de mapeo y de errores ya no usan cuerpos inventados: se prueban contra
los literales que devuelve el backend, copiados a
`frontend/src/infrastructure/mocks/payloads.reales.ts` con la referencia al
archivo del backend del que salió cada uno.

Qué se verificó:

- **Éxitos**: vehículo `AB1234`/Toyota/Corolla/2018/45000 km, orden con
  `mecanico_actual_id: null` y fechas `-03:00`, historial de usuario y de sistema
  (con `estado_anterior`, `actor_usuario_id` y `observacion` en `null`), y el
  token de login con el usuario anidado.
- **Errores de la Gateway**: los 7 códigos de su catálogo (`RUTA_NO_ENCONTRADA`,
  `METODO_NO_PERMITIDO`, `ERROR_INTERNO`, `ERROR_MICROSERVICIO`,
  `MICROSERVICIO_INALCANZABLE`, `GATEWAY_SATURADA`, `TIEMPO_AGOTADO`), con su
  `detail`, `request_id` y código.
- **Errores de los microservicios**: 409 de patente y de correo, 401 de
  credenciales y de token, 403, y los 422 en sus tres formas (lista de FastAPI y
  dos strings).

Cambios que salieron de esta prueba:

- `502/503/504` se siguen marcando como fallo de servicio, pero ahora la
  interfaz muestra el mensaje que escribió el backend ("La Gateway está
  ocupada. Intente más tarde.") en vez de un texto genérico. Antes ya se
  respetaba el `detail`; ahora está fijado con pruebas para que no se pierda.
- Se expone el `request_id` de la Gateway como `Referencia: <id>` en los estados
  de error, en el banner de servicio caído y en el formulario de registro, para
  poder rastrear el fallo en los logs. `getApiErrorRequestId` lo lee del bloque
  `error` y, si no está, de la cabecera `X-Request-ID`.
- El `409` de patente duplicada muestra el literal del servidor ("La patente ya
  está registrada") en el campo Patente, en vez de un texto propio del frontend.
- `anio` y `kilometraje` son opcionales en el contrato y llegan en `null` para un
  vehículo sin esos datos: `vehicleDisplay.ts` muestra "Sin especificar" en vez
  de "Año: 0". Limitación asumida: un vehículo con 0 km reales queda
  indistinguible de uno sin dato.
- Con `roles` múltiple en la respuesta de MS1 gana el primero (`roles[0]`), que
  es el que define el portal de ingreso. Queda documentado y fijado con un test.
- Vitest corre con `TZ: America/Santiago`, así que las pruebas de fechas con
  offset `-03:00` no dependen de la zona horaria de la máquina.

Desajuste detectado, sin modificar: el formulario exige una patente con formato
`ABCD-12`, pero el backend solo pide `min_length=1` y su test afirma que el
contrato no define patrón. La UI es más restrictiva que el servidor. Es una
decisión de producto, así que queda anotada en
`frontend/docs/contratos-openapi.md` ("Desajuste detectado: formato de patente")
para resolverla con el equipo.

| Verificación | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings |
| `npx vitest run` | 341 tests en 54 archivos, todos verdes (antes 286 en 51) |
| `npm run build` | Compila; queda el aviso preexistente de chunk > 500 kB |

## Discrepancias entre el frontend y el contrato de la API (2026-09-30)

Se auditó una por una las suposiciones del frontend contra la Gateway, los
contratos de `backend/gateway/contratos/` y los esquemas reales de MS1 y MS2.
El registro completo, con la evidencia de cada archivo del backend, quedó en
`frontend/docs/contratos-openapi.md`, sección "Registro de discrepancias entre el
frontend y el contrato de la API".

| # | Discrepancia | Impacto | Estado |
| --- | --- | --- | --- |
| D1 | El formulario exigía patente `ABCD-12`; el contrato solo pide `min_length=1`, sin patrón | La UI rechazaba el ejemplo del propio backend (`AB1234`) | Resuelta |
| D2 | El formulario no ponía tope a marca y modelo; el contrato exige `max_length=60` | La UI aceptaba texto largo y el backend respondía `422` | Resuelta |
| D3 | El formulario exigía año y kilometraje con rangos inventados; el contrato los declara `int \| None` sin cotas | No se podía registrar un vehículo sin esos datos, y valores válidos (año 1995, 1.500.000 km) quedaban fuera | Resuelta |
| D4 | Este repo afirmaba que `backend/docs/contratos-api-gateway.md` estaba desactualizado | Ya no lo estaba: la dependencia de backend lo había actualizado | Resuelta |

Cambios:

- La patente se valida con `min(1)` y su `placeholder` es `AB1234`, alineado con
  el contrato, que es la autoridad.
- `marca` y `modelo` tienen ahora `.max(60)`, como el backend. El `422` real que
  recibía el usuario por texto largo quedó como fixture
  (`textoVehiculoDemasiadoLargo`) y como prueba en `errors.test.ts`.
- Año y kilometraje son opcionales en el formulario y viajan como `null`
  explícito, el valor que el contrato declara. Se eliminaron los topes que el
  contrato nunca declaró, pero se conserva el rechazo de un valor no numérico o
  negativo.
- Se corrigió la sección que reportaba como deuda un documento del backend que
  ya estaba al día.

Queda anotado para el equipo de backend, sin tocarlo desde el frontend: el
contrato no acota `anio` ni `kilometraje` (debería declarar `ge`/`le`), y el
`origen` del historial es un `str` abierto cuando el dominio solo admite
`usuario` o `sistema`.

| Verificación | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings |
| `npx vitest run` | 347 tests en 54 archivos, todos verdes (antes 341) |
| `npm run build` | Compila; queda el aviso preexistente de chunk > 500 kB |

## Vista web del mecánico y sus órdenes asignadas (2026-10-04)

El portal `/mechanic` ya tenía las vistas de órdenes, detalle y avance de estado,
pero la misión pedía cerrar los huecos que quedaban. Se auditing cada vista contra
los endpoints reales de MS2 antes de tocar nada.

### Bugs encontrados

- **Los vehículos nunca se cargaban** en `/mechanic/ordenes` ni en
  `/mechanic/estados`: ambas páginas leían `useVehicleStore` pero ninguna llamaba
  `fetchVehicles`. Como la caché es solo en memoria, entrar directo a la ruta o
  refrescar dejaba la lista siempre en el fallback `Vehículo N°<id>`, sin patente ni
  modelo. El backend sí entregaba todo lo necesario:
  `listar_vehiculos_para_mecanico` (`services/vehiculos.py`) filtra por
  `mecanico_actual_id` **sin filtro de estado**, así que un solo
  `GET /vehiculos/asignados` etiqueta el 100% de las órdenes del mecánico.
- **La búsqueda por estado no funcionaba** en `/mechanic/ordenes`: el texto
  buscable armaba el hash sin `ordenStatusLabel`, que `AdminOrdersPage` y
  `ClientOrdersPage` sí incluyen.
- **Fuga de datos entre sesiones**: `logout()` y `clearSession()` solo limpiaban la
  sesión de auth, no las cachés de órdenes y vehículos, que son compartidas entre
  los tres portales y usan `mergeById`. Como `MechanicVehiclesPage` filtraba la
  lista completa de `vehicles` solo por texto de búsqueda, un mecánico que
  entrara en el mismo navegador tras una sesión de admin vería los vehículos
  cacheados del admin. Los comentarios del código afirmaban lo contrario.

### Cambios

- Las cuatro vistas del portal cargan sus vehículos asignados y reutilizan los
  helpers `orderVehicleLabel`/`orderPatente`.
- `/mechanic/estados` suma búsqueda, filtro por estado y paginación (reusando
  `useOrderListFilters`, `OrderListToolbar` y `OrderPagination`), y separa en un
  bloque **Órdenes cerradas** las que no tienen ningún avance del mecánico, en vez
  de mostrarles un selector sin opciones.
- El avance de estado pide confirmación con `ConfirmDialog` (componente que
  existía sin uso) y confirma el éxito con un toast.
- Nuevo sistema de toast (`ToastProvider` + `Toast`) montado en `App.tsx`, para
  los tres portales.
- `/mechanic` pasa de un texto que decía "se implementará en una próxima misión" a
  un panel con cuatro indicadores (órdenes asignadas, activas, esperan tu avance y
  vehículos asignados) más el desglose por estado. Se calculan en el cliente porque
  `GET /api/ordenes` devuelve la colección completa sin filtros ni paginación.
- Doble barrera de alcance: además de la Gateway, las vistas comparan contra
  `user.id`. Es válido porque `mecanicoActualId` y `user.id` son ambos el
  `usuario_id` de MS1 (lo usa `_filtro_visibilidad` en MS2). La lógica quedó en
  `mechanicScope.ts`. Y `logout`/`clearSession` ahora purgan las cachés
  compartidas.
- Se eliminaron `/mechanic/historial` (con su enlace de menú) y las páginas
  `MechanicHistoryPage.tsx` y `MechanicPortalPage.tsx`, que eran código muerto.
  No hay endpoint de historial por mecánico: MS2 solo expone
  `GET /api/ordenes/{id}/historial`, y el historial ya se consulta completo en
  `/mechanic/ordenes/:id`.

Se ajustaron los tests que fijaban el comportamiento anterior ("no filtrar por
identidad") y se añadieron los del panel, del toast, del alcance por mecánico y de
la purga de cachés.

| Verificación | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings |
| `npx vitest run` | 380 tests en 133 archivos, todos verdes (antes 347) |
| `npm run build` | Compila; queda el aviso preexistente de chunk > 500 kB |

## Cambios de estado desde la vista del mecánico: matriz y verificación real (2026-10-07)

La vista `/mechanic/estados` ya probaba solo el avance `5 -> 6`. Esta ronda cierra
el resto de la matriz con pruebas de frontend y confirma el ciclo contra
PostgreSQL real y los tres procesos (MS1 + MS2 + Gateway).

### Frontend (tests nuevos)

- `Order.test.ts` amarra `AVANCES_MECANICO` a los 10 pares que acepta
  `backend/services/ms2_taller/domain/transiciones_orden.py:70-111`: si se
  agrega un par que MS2 rechaza, el test falla (no lo descubre el 409 en
  pantalla). Además exige que los 4 estados sin avance del mecánico (3, 6, 7, 8)
  queden explícitos y que todo destino ofrecido tenga etiqueta.
- `MechanicStatusPage.test.tsx` sube a 30 casos: matriz de los 8 estados
  (qué opciones ofrece cada uno y cuáles caen a "Órdenes cerradas"), los 4
  avances del mecánico con observación, errores literales del backend
  (403 reasignación, 409 transición, 409 terminal, 404, 422 listado de
  FastAPI), reintento sin recargar, ausencia de doble envío con el botón en
  "Cargando...", actualización visual de la caché y alcance por `user.id`.
- `OrderService.test.ts` verifica la forma del body (`estado_destino` +
  `observacion`, sin campos extra porque el modelo usa `extra="forbid"`) y que la
  observación de solo espacios se omite (`min_length=1` con strip en MS2).

| Verificación frontend | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings (163 archivos) |
| `npx vitest run` | 417 tests en 141 suites, todos verdes (antes 387) |
| `npm run build` (tsc -b && vite build) | OK; aviso preexistente de chunk > 500 kB |

### PostgreSQL local (en vez de Docker)

Docker Desktop/WSL no estaban disponibles; se usó el PostgreSQL 18 local
(127.0.0.1:5432) que ya corría. Quedó así en `backend/.env` (gitignored, no se
sube):

- Rol `taller` (password `taller`) y bases `taller_ms1`, `taller_ms2`,
  `taller_ms3` (no existían; se crearon solo si faltaban).
- `alembic upgrade head` para MS1, MS2 y MS3, y `scripts/seed_usuarios_prueba.py`
  (idempotente) que crea cliente/mecánico/admin y el perfil Cliente en MS2.

### B1: suite pytest contra PostgreSQL real

Docker no se usa; se apuntan las suites de migración/ORM a la instancia local:

```
$env:MS2_MIGRATION_TEST_DATABASE_URL="postgresql+psycopg://taller:taller@localhost:5432/taller_ms2"
$env:MS3_ORM_TEST_DATABASE_URL="postgresql+psycopg://taller:taller@localhost:5432/taller_ms3"
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado: **488 passed, 0 skipped** (54 s). Incluye MinIO; antes de tenerlo eran
486/2 y con la suite original 427/61 (por tiempos de conexión a 5434/5435).

### MinIO (MS4) con Docker Desktop

El `docker-compose` de MS4 usa `cgr.dev/chainguard/minio` (servidor) y
`quay.io/minio/mc` (cliente `minio_init`); este último ahora responde **401
UNAUTHORIZED** en los pulls (el repo/tag ya no se sirve sin auth). Workaround
verificado (2026-10-07):

```
docker volume create minio_data
docker run -d --name sgtm_minio `
  -e MINIO_ROOT_USER=admin-local -e MINIO_ROOT_PASSWORD=cambia-esta-clave-local `
  -p 9000:9000 -p 9001:9001 `
  -v minio_data:/data -v "$PWD\minio:/config:ro" `
  cgr.dev/chainguard/minio@sha256:999718c09ef5d2ac888aa97ffd628a67ba8be2d64d6eea9e719d1f58cd59e204 `
  server /data --console-address ":9001"
```

El binario `mc` viene incluido en la imagen de Chainguard (lo usa su healthcheck),
así que el setup de `minio_init` se replica con `docker exec sgtm_minio mc
--config-dir /tmp/mc-live ...`: alias `sgtm`, bucket `evidencias` privado, usuario
`ms4-evidencias`, y la política `politica-ms4` desde `/config/politica-ms4.json`
(montada en ro). Verificado con `mc admin user info` (PolicyName: politica-ms4) y
con la suite: `test_ms4_minio_integracion` y `test_ms4_recepcion_minio` en verde.

### B2: ciclo completo contra el stack real (Gateway 8000, MS1 8001, MS2 8002)

Script temporal (borrado al terminar); cada paso se ejecutó con el token real de
MS1 a través de `PATCH /api/ordenes/{id}/estado`. Resultado: **20/20 PASS**.

- Login de admin, cliente y mecánico (3 JWTs), alta de vehículo (cliente)
  y de orden (admin).
- Ciclo de la orden asignada: asignar mecánico mueve `1 -> 2` automáticamente;
  luego mecánico `2 -> 3`, admin `3 -> 5`, mecánico `5 -> 6`, admin `6 -> 7`.
- El historial registra 6 entradas con el actor correcto (mecánico en 2->3 y 5->6;
  admin en las demás) y `origen="usuario"`.
- Rechazos verificados con el literal exacto del backend:
  - terminal: 409 `El estado Entregado es terminal y no admite transiciones`
  - transición inválida: 409 `Transición no permitida: Recibido -> En reparación`
  - no autorizado: 403 `No tienes permiso para cambiar el estado de esta orden`
  - inexistente: 404 `Orden no encontrada`
  - destino desconocido: 422 `Estado de destino desconocido: 999`
  - esquema: 422 con `detail` list (p. ej. `estado_destino: 0`)
- Tras los rechazos la orden sigue en estado 1 (rollback correcto).

Los literales 403/409/404/422 coinciden con los fixtures de
`frontend/src/infrastructure/mocks/payloads.reales.ts` que usan los tests de la
vista, así que los tests de UI y la verificación real validan el mismo contrato.

Nota: al correr desde una consola de Python en Windows, el keep-alive de httpx
contra uvicorn se cae al reutilizar el socket (WinError 10054); el script usó
`httpx.Limits(max_keepalive_connections=1, keepalive_expiry=0)`. Correr pytest
solo también exige que el puerto 5432 esté libre y las 3 bases migradas.
