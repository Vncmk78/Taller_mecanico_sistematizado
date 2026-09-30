# Backend SGTM — Sistema de Gestión de Talleres Mecánicos

Grupo 10 · Taller de Integración II · Universidad Católica de Temuco

Repositorio único con **cuatro microservicios independientes**, cada uno con su
propia base de datos PostgreSQL. No existen claves foráneas físicas entre bases
de servicios distintos: esas relaciones son lógicas y se resuelven por contrato
de API (Sistematización final §1.2 y §8).

## Estructura

```
backend/
├── gateway/                 API Gateway: único punto de entrada del backend
│   ├── config.py            Variables de entorno (prefijo GATEWAY_)
│   ├── rutas.py             Tabla de enrutamiento (prefijo -> microservicio)
│   ├── main.py              Crea la app, CORS y monta los routers
│   └── routers/
│       ├── health.py        GET /  y  GET /api/health (endpoints propios)
│       └── proxy.py         Reenvío de /api/* hacia los microservicios
├── shared/                  Código común: configuración y fábrica de persistencia
│   ├── config.py            ServiceSettings (DATABASE_URL, DB_ECHO, pool)
│   └── db.py                crear_base / crear_engine / crear_session_factory
├── services/
│   ├── ms1_auth/            Autenticación, usuarios, roles, sesiones y notificaciones
│   ├── ms2_taller/          Vehículos, ingresos, órdenes, estados y capacidad
│   ├── ms3_presupuestos/    Presupuestos, repuestos, proveedores e inventario
│   └── ms4_evidencias/      Metadatos de evidencia multimedia
│       ├── config.py        Variables de entorno con prefijo MS4_
│       ├── db.py            Base, engine, SessionLocal y get_db de ESTE servicio
│       ├── models/          Modelos ORM del servicio
│       ├── alembic/         Migraciones propias del servicio
│       ├── routers/         Endpoints de negocio (en desarrollo)
│       ├── schemas/         Schemas Pydantic de evidencias (en desarrollo)
│       ├── services/        Lógica de dominio (cliente S3; sha256 y confirmación en la tarea de recepción)
│       └── main.py          App FastAPI con healthchecks
├── docker-compose.yml       Cuatro PostgreSQL: puertos 5433, 5434, 5435, 5436
├── verificar_conexion.py    Prueba las cuatro conexiones de una sola vez
└── requirements.txt
```

Cada servicio tiene su **propia base declarativa**. Es lo que impide que las
tablas de los cuatro dominios terminen mezcladas en una misma migración.

## Puesta en marcha

```bash
cd backend

# 1. Entorno virtual e instalación de dependencias
python -m venv .venv
.venv\Scripts\activate            # Windows   (en Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env            # Windows   (en Linux/macOS: cp .env.example .env)

# 3. Levantar las cuatro bases
docker compose up -d
docker compose ps                 # las cuatro deben aparecer como "healthy"

# 4. Comprobar que los cuatro servicios se conectan a su base
python verificar_conexion.py
```

Salida esperada del paso 4:

```
[OK]    MS1 — Autenticación y Usuarios  ->  PostgreSQL 16.x
[OK]    MS2 — Vehículos y Órdenes de Trabajo  ->  PostgreSQL 16.x
[OK]    MS3 — Presupuestos, Repuestos y Proveedores  ->  PostgreSQL 16.x
[OK]    MS4 — Evidencia Multimedia  ->  PostgreSQL 16.x

Las cuatro conexiones responden.
```

## Levantar un servicio

```bash
uvicorn services.ms1_auth.main:app --reload --port 8001
uvicorn services.ms2_taller.main:app --reload --port 8002
uvicorn services.ms3_presupuestos.main:app --reload --port 8003
uvicorn services.ms4_evidencias.main:app --reload --port 8004
```

Cada servicio publica `GET /health` (el proceso responde) y `GET /health/db`
(su base responde), además de su documentación OpenAPI en `/docs`.

Los comandos se ejecutan **desde `backend/`**, porque los imports son
`services.<paquete>...` y `shared...`.

## MS3 — Presupuestos, Repuestos y Proveedores

MS3 guarda presupuestos versionados, repuestos, proveedores e inventario en su
propia base. Las reglas de versionado (versión enviada congelada, bloqueo al
aprobar, decisión inmutable) las garantiza la base con triggers.

```bash
# 1. Migrar la base de MS3 (requiere MS3_JWT_SECRET_KEY en el entorno: ver .env)
alembic -c services/ms3_presupuestos/alembic.ini upgrade head

# 2. Datos de prueba (idempotente): proveedores, repuestos, umbral e inventario.
#    Con --orden-id agrega un presupuesto de ejemplo (versión 1 enviada).
python scripts/seed_datos_ms3.py --orden-id 1

# 3. Pruebas de persistencia ORM contra PostgreSQL migrado (se omiten si no hay base)
MS3_ORM_TEST_DATABASE_URL=postgresql+psycopg://taller:taller@localhost:5435/taller_ms3 \
    pytest services/ms3_presupuestos/tests -q
```

### Patrón de persistencia de MS3 (sesión, repositorio y transacciones)

`services/ms3_presupuestos/persistencia/`:

- `repositorios.py`: un repositorio por agregado (proveedores, repuestos,
  movimientos, parámetros, presupuestos). Consultan y agregan, **nunca hacen commit**.
- `unidad_de_trabajo.py`: `UnidadDeTrabajo` reúne los repositorios sobre una
  misma sesión. Todo caso de uso va dentro de `with uow.transaccion():` →
  commit al final o rollback si algo falla (anidado = SAVEPOINT).
- `errores.py`: traduce los errores de PostgreSQL (UNIQUE, FK, CHECK, triggers)
  a `ConflictoDeDatos` (409), `ReglaDeDatosViolada` (422) y `RecursoNoEncontrado`
  (404); `main.py` los convierte en respuestas HTTP sin exponer SQL.

```python
def registrar_proveedor(uow: UnidadDeTrabajo, nombre: str, contacto: str) -> Proveedor:
    with uow.transaccion():
        return uow.proveedores.agregar(Proveedor(nombre=nombre, contacto=contacto))

@router.post("", status_code=201)
def crear(body: ProveedorCrear, uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo)):
    return registrar_proveedor(uow, body.nombre, body.contacto)   # 409 si el nombre ya existe
```

## MS4 — Evidencia Multimedia

MS4 guarda los **metadatos** de las evidencias (fotos/videos) en su propia base;
los **archivos** viven en MinIO/S3 (bucket `evidencias`, usuario `ms4-evidencias`).
Para migrar su base y levantar el servicio:

```bash
# Migrar la base de MS4 (requiere MS4_JWT_SECRET_KEY en el entorno: ver .env)
alembic -c services\ms4_evidencias\alembic.ini upgrade head

# Levantar el servicio (no olvides levantar minio: docker compose up -d minio minio_init)
uvicorn services.ms4_evidencias.main:app --reload --port 8004

# Comprobar la salud del proceso, la base y el almacenamiento
curl localhost:8004/health
curl localhost:8004/health/db
curl localhost:8004/health/storage
```

`/health/storage` responde 200 cuando el bucket S3 responde y 503 con un mensaje
genérico en cualquier otro caso (sin filtrar endpoint ni claves).

## API Gateway

El frontend (React) y la app móvil no llaman directo a los microservicios: lo
hacen a la **Gateway**, que expone el mismo camino `/api/*` y reenvía a cada
microservicio según el primer segmento de la ruta (sin conocer reglas de
negocio, preservando el aislamiento entre bases).

```bash
uvicorn gateway.main:app --reload --port 8000
```

Tabla de enrutamiento (primer segmento → microservicio):

| Segmento                  | Microservicio |
| ------------------------- | ------------- |
| `/api/auth/*`             | MS1 (auth)    |
| `/api/vehiculos/*`, `/api/ordenes/*`, `/api/clientes/*`, `/api/mecanicos/*` | MS2 (taller) |
| `/api/presupuestos/*`, `/api/repuestos/*`, `/api/proveedores/*`, `/api/inventario/*` | MS3 (presupuestos) |
| `/api/evidencias/*`       | MS4 (multimedia) |

Las URLs de los servicios se configuran en `.env` con el prefijo `GATEWAY_`
(`GATEWAY_MS1_URL=...`, etc.); por defecto apuntan a `localhost:8001-8004`.
Salud: `GET /api/health` responde sin depender de las bases.

## Cómo usar la persistencia en un endpoint

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db

@app.get("/vehiculos")
def listar(db: Session = Depends(get_db)):
    ...
```

`get_db` abre una sesión por petición, hace `rollback` si el endpoint lanza una
excepción y cierra siempre la conexión.

## Cómo agregar un modelo

1. Crear el archivo en `services/<servicio>/models/` heredando de la `Base` de
   **ese** servicio (`from services.<servicio>.db import Base`).
2. Importarlo en `services/<servicio>/models/__init__.py`, o Alembic no lo verá.
3. Los nombres de tablas y campos salen de la lámina `04-mer-erd`, del recuadro
   de la base que corresponda.

Un modelo nunca importa la `Base` de otro servicio ni declara un `ForeignKey`
hacia una tabla de otra base: esas referencias se guardan como identificador
suelto (los campos marcados `REF` en el MER) y se resuelven por API.

## Convenciones

- Nombres de tablas y columnas en minúsculas y en español, como en el MER.
- Nombres de índices y restricciones generados por la convención de
  `shared/db.py`, para que las migraciones sean idénticas en todas las máquinas.
- El archivo `.env` nunca se sube al repositorio; sí se sube `.env.example`.

## Historial

`_legacy_monolito_20260907/` conserva el primer intento con una sola base y con
el rol como enumeración dentro de `Usuario`. Se reemplazó porque la
sistematización final define cuatro bases independientes (§1.2) y roles
múltiples por usuario mediante `Usuario` / `UsuarioRol` / `Rol` (§1.1). Se deja
como referencia y se puede borrar cuando el equipo lo confirme.
