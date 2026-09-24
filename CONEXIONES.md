# CONEXIONES ÔÇö Despliegue Vercel + Neon + Usuarios de prueba

Documento de conexi├│n del SGTM desplegado en **Vercel** con base de datos
**Neon** (PostgreSQL serverless) y los cuatro microservicios tras un API
Gateway. Este documento es la fuente de verdad para el equipo: define los
endpoints p├║blicos, las variables de entorno, los usuarios de prueba y los
pasos de despliegue.

---

## 1. Arquitectura desplegada

```
https://<proyecto>.vercel.app/
Ôö£ÔöÇÔöÇ /            ÔåÆ Frontend Web (React + Vite) [servicio Vercel: frontend]
Ôö£ÔöÇÔöÇ /api/*       ÔåÆ API Gateway (FastAPI)      [servicio Vercel: backend]
Ôöé                  ÔööÔöÇ proxya a MS1..MS4 seg├║n el primer segmento:
Ôöé                     /api/auth/*        ÔåÆ ms1 (auth)
Ôöé                     /api/vehiculos/*   ÔåÆ ms2 (taller)
Ôöé                     /api/ordenes/*     ÔåÆ ms2
Ôöé                     /api/clientes/*    ÔåÆ ms2
Ôöé                     /api/mecanicos/*   ÔåÆ ms2
Ôöé                     /api/presupuestos* ÔåÆ ms3
Ôöé                     /api/evidencias/*  ÔåÆ ms4
Ôö£ÔöÇÔöÇ /ms1/docs     ÔåÆ OpenAPI/Swagger de MS1 (acceso directo al servicio)
Ôö£ÔöÇÔöÇ /ms2/docs     ÔåÆ OpenAPI/Swagger de MS2
Ôö£ÔöÇÔöÇ /ms3/docs     ÔåÆ OpenAPI/Swagger de MS3
Ôö£ÔöÇÔöÇ /ms4/docs     ÔåÆ OpenAPI/Swagger de MS4
ÔööÔöÇÔöÇ /docs         ÔåÆ OpenAPI/Swagger de la Gateway
```

Definici├│n de servicios en `vercel.json` (modelo Vercel Services):

| Servicio | Root | Entrypoint | URL p├║blica |
| --- | --- | --- | --- |
| `frontend` | `frontend` | ÔÇö (Vite) | `/` |
| `backend` (Gateway) | `backend` | `gateway/main:app` | `/api/*`, `/docs` |
| `ms1` | `backend` | `services/ms1_auth/main:app` | `/ms1/*` |
| `ms2` | `backend` | `services/ms2_taller/main:app` | `/ms2/*` |
| `ms3` | `backend` | `services/ms3_presupuestos/main:app` | `/ms3/*` |
| `ms4` | `backend` | `services/ms4_evidencias/main:app` | `/ms4/*` |

La gateway enlaza los microservicios con **bindings de servicio**:
`GATEWAY_MS1_URL` ÔÇª `GATEWAY_MS4_URL` (los resuelve Vercel al desplegar).

---

## 2. Endpoints p├║blicos

### 2.1 Gateway (todo el mundo pasa por ac├í)

| M├®todo | Ruta | Descripci├│n |
| --- | --- | --- |
| `GET` | `/api/health` | Estado de la Gateway |
| `POST` | `/api/auth/register` | Registro p├║blico (rol Cliente) |
| `POST` | `/api/auth/login` | Login ÔåÆ JWT + usuario con roles |
| `GET` | `/api/auth/me` | Usuario autenticado (requiere token) |
| `GET` | `/api/vehiculos/mios` | Veh├¡culos del cliente autenticado (token) |
| `GET` | `/api/vehiculos` | Lista de veh├¡culos (token + rol) |
| `GET` | `/api/vehiculos/{id}` | Detalle de un veh├¡culo (token) |
| `POST` | `/api/vehiculos` | Registra un veh├¡culo (token) |
| `PATCH` | `/api/vehiculos/{id}` | Actualiza un veh├¡culo (token) |

### 2.2 Acceso directo a cada microservicio

| URL | Descripci├│n |
| --- | --- |
| `<base>/ms1/docs` | Swagger MS1 (auth) |
| `<base>/ms1/health` | Health MS1 |
| `<base>/ms2/docs` | Swagger MS2 (taller: veh├¡culos, ├│rdenes, clientes, mec├ínicos) |
| `<base>/ms2/health` | Health MS2 |
| `<base>/ms3/docs` | Swagger MS3 (presupuestos, repuestos, proveedores, inventario) |
| `<base>/ms3/health` | Health MS3 |
| `<base>/ms4/docs` | Swagger MS4 (evidencias) |
| `<base>/ms4/health` | Health MS4 |
| `<base>/docs` | Swagger de la Gateway |

> Para la **app m├│vil** usar siempre `<base>/api/*`: el consumo es id├®ntico al
> frontend web.

---

## 3. Usuarios de prueba (web y m├│vil)

Usuarios sembrados con `backend/scripts/seed_usuarios_prueba.py` (idempotente).

| Rol | Correo | Contrase├▒a |
| --- | --- | --- |
| **Cliente** | `cliente@pruebas.cl` | `ClientePrueba123!` |
| **Mec├ínico** | `mecanico@pruebas.cl` | `MecanicoPrueba123!` |
| **Administrador** | `administrador@pruebas.cl` | `AdminPrueba123!` |

- El usuario **Cliente** tiene perfil creado en MS2 (para usar `/api/vehiculos/mios`).
- Los roles provienen de la migraci├│n `0002_roles_iniciales_ms1`
  (`cliente`, `mecanico`, `administrador`).

---

## 4. Base de datos Neon

Cuatro bases independientes, una por microservicio (┬º8 aislaci├│n de datos):

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

Pasos en Neon:
1. Crear un proyecto Neon (una instancia de Postgres).
2. En el proyecto, crear **4 bases**: `taller_ms1`, `taller_ms2`, `taller_ms3`, `taller_ms4`.
3. Copiar cada cadena de conexi├│n (Pooled o Direct) a las variables de Vercel
   (Secci├│n 5) a├▒adiendo `?sslmode=require`.

### Migraciones contra Neon

Con `backend/.env` apuntando a Neon (los servicios leen `MSn_DATABASE_URL`):

```powershell
cd backend
.\scripts\migrar_neon.ps1
```

Aplica las migraciones de MS1, MS2 y MS3 (`alembic upgrade head`). MS4 todav├¡a
no tiene migraciones (no hay modelos). El seed DEBE ejecutarse despu├®s:

```powershell
python scripts/seed_usuarios_prueba.py
```

---

## 5. Variables de entorno en Vercel

En el proyecto de Vercel, configurar como Environment Variables (Production):

| Variable | Valor |
| --- | --- |
| `MS1_DATABASE_URL` | DSN Neon base `taller_ms1` con `?sslmode=require` |
| `MS2_DATABASE_URL` | DSN Neon base `taller_ms2` con `?sslmode=require` |
| `MS3_DATABASE_URL` | DSN Neon base `taller_ms3` con `?sslmode=require` |
| `MS4_DATABASE_URL` | DSN Neon base `taller_ms4` con `?sslmode=require` |
| `MS1_JWT_SECRET_KEY` | Clave aleatoria ÔëÑ 32 caracteres (HS256, compartida con MS2) |
| `MS2_JWT_SECRET_KEY` | La MISMA clave que `MS1_JWT_SECRET_KEY` |
| `MS1_JWT_ALGORITHM` | `HS256` |
| `MS2_JWT_ALGORITHM` | `HS256` |
| `GATEWAY_CORS_ORIGINS` | `https://<proyecto>.vercel.app` (or├¡genes extra, opcional) |

> `GATEWAY_MS1_URLÔÇªGATEWAY_MS4_URL` **no se escriben a mano**: las crea Vercel
> autom├íticamente con los bindings de servicio definidos en `vercel.json`.

Generar clave JWT:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 6. Pasos de despliegue (Vercel)

1. Hacer merge de la rama de trabajo (`Gustavo`) a `Develop` y luego a `main`.
2. En Vercel: **Add New ÔåÆ Project**, importar el repo desde la rama `main`.
3. Vercel detecta el `vercel.json` con los servicios. No es necesario build
   command manual (Vite y FastAPI se detectan por framework).
4. Agregar las variables de entorno de la Secci├│n 5.
5. Deploy. Vercel crea los servicios `frontend`, `backend`, `ms1`ÔÇª`ms4` y los
   bindings de red internos autom├íticamente.
6. Configurar Neon (Secci├│n 4) y ejecutar migraciones + seed una vez que el
   proyecto est├® creado.
7. Verificar:
   - `GET <base>/api/health` ÔåÆ `{"status":"ok"}`
   - `POST <base>/api/auth/login` con `cliente@pruebas.cl` ÔåÆ token JWT.
   - `<base>/ms1/docs` carga Swagger MS1.
   - Abrir `<base>/` ÔåÆ Login del frontend funciona (relative `/api`).

### Despliegue local (desarrollo)

```powershell
# Backend (tuiliz├í un .env local con DSNs locales)
cd backend
uvicorn gateway.main:app --reload --port 8000
# Microservicios por separado (para desarrollo)
uvicorn services.ms1_auth.main:app --reload --port 8001
uvicorn services.ms2_taller.main:app --reload --port 8002
uvicorn services.ms3_presupuestos.main:app --reload --port 8003
uvicorn services.ms4_evidencias.main:app --reload --port 8004

# Frontend (el proxy de Vite reenv├¡a /api ÔåÆ localhost:8000)
cd frontend
npm run dev
```

---

## 7. Notas t├®cnicas

- **CORS**: la Gateway expone `Access-Control-Allow-Origin`. En Vercel el
  frontend y la API comparten origen, pero la app m├│vil o previews
  `*.vercel.app` quedan cubiertos por `allow_origin_regex`.
- **Paths relativos**: el frontend usa `baseURL '/api'`; en producci├│n se
  resuelve contra el mismo dominio. `VITE_API_URL` queda disponible para
  sobreescribir (ej. `https://<proyecto>.vercel.app/api`).
- **JWT**: HS256 compartido entre MS1 (genera) y MS2 (valida). Nunca subir los
  secrets al repositorio.
- Archivos relacionados: `vercel.json` (servicios), `backend/.env.example`
  (plantilla de variables), `backend/scripts/migrar_neon.ps1`,
  `backend/scripts/seed_usuarios_prueba.py`.
