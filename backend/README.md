# Backend SGTM — Sistema de Gestión de Talleres Mecánicos

Grupo 10 · Taller de Integración II · Universidad Católica de Temuco

Repositorio único con **cuatro microservicios independientes**, cada uno con su
propia base de datos PostgreSQL. No existen claves foráneas físicas entre bases
de servicios distintos: esas relaciones son lógicas y se resuelven por contrato
de API (Sistematización final §1.2 y §8).

## Estructura

```
backend/
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
│       ├── models/          Modelos ORM del servicio (se llenan en la tarea de modelos)
│       ├── alembic/         Migraciones propias del servicio
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
