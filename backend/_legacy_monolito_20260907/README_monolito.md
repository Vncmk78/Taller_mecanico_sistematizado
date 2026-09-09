# Backend — Sistema de Gestión de Taller (Grupo 10)

Base de persistencia del proyecto (Semana 1). Stack según *Herramientas a
utilizar*: **FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL**.

Este entregable cubre los dos tickets de Semana 1 de Martín López:

1. **Conexión BD y estructura de persistencia mediante ORM** → `app/core/`
2. **Sistema de migraciones + modelos ORM de Usuario, Rol, Cliente y Vehículo**
   → `app/models/` y `alembic/`

## Estructura

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py       # settings (.env) con pydantic-settings
│   │   └── database.py     # engine + SessionLocal + get_db()
│   ├── models/
│   │   ├── base.py         # Base declarativa (SQLAlchemy 2)
│   │   ├── enums.py        # RolUsuario (cliente|mecanico|admin)
│   │   ├── usuario.py      # Usuario (con rol)
│   │   ├── cliente.py      # Cliente
│   │   └── vehiculo.py     # Vehículo
│   └── main.py             # API mínima (healthchecks)
├── alembic/                # migraciones
│   ├── env.py
│   └── versions/0001_inicial.py
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Puesta en marcha

```bash
# 1. Entorno e instalación
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configuración
cp .env.example .env             # ajusta DATABASE_URL a tu PostgreSQL

# 3. Crear la base (una vez, en PostgreSQL)
#    createdb taller   (o CREATE DATABASE taller; desde psql)

# 4. Migraciones
alembic upgrade head             # crea las tablas usuario, cliente, vehiculo

# 5. Levantar la API
uvicorn app.main:app --reload
#   http://localhost:8000/health      -> {"status":"ok"}
#   http://localhost:8000/health/db   -> {"database":"ok"}
#   http://localhost:8000/docs        -> Swagger
```

## Migraciones (Alembic)

```bash
alembic revision --autogenerate -m "descripcion"   # generar nueva migración
alembic upgrade head                               # aplicar
alembic downgrade -1                               # revertir la última
```

La URL de la base **no** vive en `alembic.ini`; `alembic/env.py` la toma de
`app.core.config` (variable `DATABASE_URL`), así no se duplican credenciales.

## Nota sobre el modelo "Rol"

El MER define `rol` como un campo enumerado del `Usuario`
(`cliente | mecanico | admin`). Para no romper el esquema acordado por el equipo
se implementó como un `Enum` (`app/models/enums.py`) en vez de una tabla `Rol`
separada. Si el equipo prefiere normalizarlo en una tabla aparte, es un cambio
acotado (nuevo modelo + FK + migración).
