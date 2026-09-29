# MS3 · Microservicio de Presupuestos, Repuestos y Proveedores

Microservicio Python/FastAPI del sistema **Taller Mecánico Sistematizado**
(ver `Sprint 0 - Entregables/01-arquitectura.png`). Gestiona presupuestos por
orden, sus repuestos, los proveedores y los parámetros de inventario.

Es un servicio **independiente y autocontenido**, con su propia base de datos
PostgreSQL, igual que `auth-service`. No comparte base ni claves foráneas con
otros servicios: las referencias a MS1 (usuarios) y MS2 (órdenes) son lógicas y
se resuelven por contrato de API (Sistematización final §8).

## Arquitectura

Arquitectura hexagonal, igual que el frontend (RNF-01) y `auth-service`:

```
app/
├── domain/            # Entidades puras del dominio (sin dependencias externas)
│   └── entities/      # Proveedor, Repuesto, Presupuesto, ParametroInventario
├── infrastructure/    # Adaptadores concretos
│   ├── config.py      # Configuración desde .env (DATABASE_URL, CORS)
│   └── db/            # SQLAlchemy: engine, sesión y modelos ORM
└── main.py            # App FastAPI con healthchecks
alembic/               # Sistema de migraciones (Alembic)
```

## Modelos ORM iniciales

Según la lámina `04-mer-erd`, recuadro "BD MS3", y §§4.3 y 4.6:

- **Proveedor** — proveedor de repuestos.
- **Repuesto** — repuesto con stock y umbral propio; FK local a Proveedor.
- **Presupuesto** — cabecera de presupuesto; `orden_id` es una REF lógica a MS2 (sin FK física).
- **ParametroInventario** — umbral general de inventario vigente.

Las versiones de presupuesto, ítems, movimientos de inventario y demás entidades
del dominio se agregan en tareas siguientes.

## Migraciones (Alembic)

La estructura de la base se administra con Alembic (no con `create_all`). Los
comandos se ejecutan desde la carpeta del servicio:

```bash
alembic upgrade head                      # aplica las migraciones
alembic revision --autogenerate -m "..."  # genera una nueva migración
```

## Puesta en marcha

```bash
cd presupuestos-service
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env            # Windows   (Linux/macOS: cp .env.example .env)
docker compose up -d presupuestos-db
alembic upgrade head
uvicorn app.main:app --reload --port 8003
```

Healthchecks: `GET /health` (el proceso responde) y `GET /health/db` (la base
responde). Documentación OpenAPI en `/docs`.
