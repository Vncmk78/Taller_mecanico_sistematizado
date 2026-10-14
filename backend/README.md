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

### Datos mínimos y fixtures de prueba de MS3

- `services/ms3_presupuestos/datos_prueba.py`: **única fuente** del catálogo de
  prueba (2 proveedores, 4 repuestos, umbral general 5, presupuesto de ejemplo
  de $68.990). La usan la semilla y las pruebas.
- `services/ms3_presupuestos/tests/fabricas.py`: fábricas que crean lo mínimo
  válido (`nuevo_repuesto`, `nuevo_movimiento`, `nuevo_presupuesto(estado=...)`,
  `enviar`, `decidir`...) con nombres y órdenes únicos.
- Fixtures en `tests/conftest.py`: `uow`, `catalogo`, `repuesto_bajo_umbral`,
  `umbral_general`, `presupuesto_borrador` / `_enviado` / `_aprobado` /
  `_rechazado` y `presupuesto_ejemplo`. Todo se revierte al terminar cada prueba.

```python
def test_no_se_edita_un_presupuesto_aprobado(presupuesto_aprobado, uow):
    ...
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

### Endpoints de presupuestos (MS3)

Requieren JWT. Por la Gateway se llaman con prefijo `/api`. El cliente solo ve
presupuestos de **sus** órdenes (MS3 lo confirma con `GET {MS3_MS2_URL}/ordenes/{id}`
reenviando su JWT; si MS2 no responde → `503`) y solo versiones ya enviadas.

| Método y ruta | Qué hace |
|---|---|
| `POST /presupuestos` | Crea el presupuesto de una orden con su versión 1 en borrador (`409` si la orden ya tiene) |
| `GET /presupuestos?orden_id=&desde=&limite=` | Lista paginada (más recientes primero) o el de una orden |
| `GET /presupuestos/{id}` | Detalle con todas las versiones, ítems, totales y decisión |
| `GET /presupuestos/{id}/versiones/{n}` | Una versión |
| `POST /presupuestos/{id}/versiones` | Crea la versión siguiente **sin tocar las anteriores**: copia los ítems de la última (o de `{"copiar_de": n}`) o usa `{"items": [...]}` |
| `PUT /presupuestos/{id}/versiones/{n}/items` | Reemplaza los ítems de un borrador (`409` si ya fue enviada) |
| `POST /presupuestos/{id}/versiones/{n}/envio` | **Administrador**: envía la última versión (con ítems y precios); queda congelada |
| `POST /presupuestos/{id}/versiones/{n}/decision` | **Cliente dueño**: `{"decision": "aprobado"}` o `{"decision": "rechazado", "motivo": "...", "confirmar_cancelacion": true}` |
| `GET /presupuestos/decisiones/{decision_id}` | **Cliente responsable**: hecho persistido que MS2 verifica antes de aplicar la decisión |
| `POST /presupuestos/decisiones/{decision_id}/aplicacion` | **Cliente responsable**: reintenta la misma decisión, sin crear otra |

Reglas de versiones (§4.3): una corrección de una versión enviada sin decisión
la reemplaza (ya no se decide sobre la anterior); después de una aprobación la
nueva versión es una modificación (`es_modificacion`) y, mientras no se apruebe,
sigue vigente la última aprobada; solo puede haber un borrador abierto (`409`);
si el primer presupuesto fue rechazado (servicio cancelado) no se crean más
versiones (`409`). Las versiones anteriores, sus ítems y decisiones nunca se
modifican: la base lo impide además con los triggers de `0003_ms3`.

Envío y decisión son **transaccionales dentro de MS3**: bloquean el presupuesto
(`SELECT ... FOR UPDATE`), validan y escriben todo junto. Tras confirmar la
primera decisión, MS3 solicita su aplicación en MS2. Un fallo posterior no
revierte la decisión: responde `503` con `decision_id` y la ruta de reintento.
MS2 verifica el hecho con el JWT original y confirma estado e historial en su
propia transacción, con idempotencia persistida. Véase
[el contrato de coordinación](docs/maquina-estados-ordenes.md#61-primera-decisión-de-presupuesto-scrum-397-y-scrum-438).
Responden
`efecto_en_orden`, lo que corresponde aplicar a la orden en MS2 (§4.2):

| Operación | `efecto_en_orden` |
|---|---|
| Primer envío | `esperando_aprobacion` |
| Envío de una modificación posterior a una aprobación | `null` (la orden no cambia) |
| Aprobar con stock suficiente | `en_reparacion` |
| Aprobar con stock insuficiente | `esperando_repuestos` (+ `repuestos_faltantes`) |
| Rechazar antes de la primera aprobación (exige `confirmar_cancelacion`) | `cancelado` |
| Rechazar una modificación | `null` (sigue vigente la última aprobada) |

```json
POST /presupuestos
{"orden_id": 1, "items": [
  {"tipo": "repuesto", "repuesto_id": 1, "descripcion": "Pastillas", "cantidad": "1", "precio_unitario": "38990"},
  {"tipo": "mano_de_obra", "descripcion": "Cambio de pastillas", "cantidad": "1.5", "precio_unitario": "20000"}
]}
```

Montos y cantidades se devuelven como texto decimal (`"68990.00"`). Cada versión
informa su `estado` (`borrador`, `enviada`, `aprobada`, `rechazada`) y el
presupuesto su `version_vigente` (última aprobada). Capas: `routers/presupuestos.py`
→ `services/presupuestos.py` (una transacción por caso de uso) →
`persistencia/` (repositorio + unidad de trabajo) → modelos ORM.

### Proveedores y repuestos (MS3)

Lectura: Mecánico y Administrador. Escritura: solo Administrador. Cliente → `403`.

| Método y ruta | Qué hace |
|---|---|
| `GET /proveedores?q=&con_repuestos=&desde=&limite=` | Lista / busca por nombre o contacto; `con_repuestos=true/false` |
| `GET /proveedores/{id}` | Detalle con sus repuestos |
| `POST /proveedores` · `PATCH /proveedores/{id}` | Alta y cambios (`409` si el nombre ya existe, sin distinguir mayúsculas) |
| `DELETE /proveedores/{id}` | Solo si no tiene repuestos (`409`) |
| `GET /repuestos?proveedor_id=&q=&bajo_umbral=&con_stock=&ordenar=&desde=&limite=` | Lista con `umbral_efectivo` y `bajo_umbral`; `bajo_umbral=true` = alerta de stock bajo; `con_stock=true/false`; `ordenar=nombre\|stock_asc\|stock_desc` |
| `GET /repuestos/{id}` | Detalle |
| `POST /repuestos` | Alta `{"proveedor_id", "nombre", "stock_inicial", "umbral_particular"}`; el stock inicial deja un movimiento `ingreso` |
| `PATCH /repuestos/{id}` | Nombre, proveedor o `umbral_particular` (`null` = volver al general); cada cambio de umbral queda en `historial_umbral` |
| `DELETE /repuestos/{id}` | Solo si nunca tuvo movimientos, presupuestos ni cambios de umbral (`409`) |

**Búsqueda (`q`)**: "contiene el texto" sin distinguir mayúsculas ni tildes
(`bujia` encuentra `Bujía`); `%` y `_` se buscan literalmente. La migración
`0006_ms3` instala `pg_trgm` y `unaccent` (extensiones *trusted*: no requieren
superusuario, funcionan en Neon), crea `ms3_normalizar(text)` y estos índices:

| Índice | Para qué |
|---|---|
| `ix_repuesto_nombre_trgm`, `ix_proveedor_nombre_trgm`, `ix_proveedor_contacto_trgm` | GIN de trigramas: `q` (`LIKE '%texto%'`) |
| `ix_repuesto_nombre_orden`, `ix_proveedor_nombre_orden` | Listar ordenado por nombre y paginar |
| `uq_proveedor_nombre_ci` | Proveedor único sin distinguir mayúsculas |
| `uq_repuesto_proveedor_nombre` (0005), `ix_repuesto_proveedor_id` | Filtro por proveedor |

Con 100.000 repuestos, buscar `q=bujia modelo 4242` tarda ~9 ms con el índice y
~217 ms sin él. `test_busquedas_catalogo.py` verifica con `EXPLAIN` que la
consulta real del repositorio usa cada índice.

El **stock no se edita** por estos endpoints: cambia solo con movimientos de
inventario. Un proveedor no puede tener dos repuestos con el mismo nombre
(migración `0005_ms3`: índice único `(proveedor_id, lower(nombre))`).

### Inventario y stock (MS3)

- **stock**: unidades físicas. Solo lo cambian `ingreso`, `ajuste` y `consumo`.
- **comprometido**: reservado para órdenes (compromisos − liberaciones − consumos, por orden).
- **disponible** = stock − comprometido. No se ofrecen las mismas unidades a dos órdenes (§4.6).

| Método y ruta | Qué hace |
|---|---|
| `POST /inventario/movimientos` | `{"clave_operacion", "repuesto_id", "tipo", "cantidad", "orden_id"?}`. Ingreso/ajuste: Administrador. Compromiso/consumo/liberación (con `orden_id`): Mecánico o Administrador. `409` si no alcanza el stock. La misma `clave_operacion` reenviada devuelve el original (`200`, `repetido: true`) sin descontar dos veces |
| `GET /inventario/movimientos?repuesto_id=&orden_id=&tipo=` | Historial de movimientos |
| `GET /inventario/stock/{repuesto_id}` | Stock, comprometido por orden, disponible y si está bajo el umbral |
| `GET /inventario/alertas` | Repuestos con stock < umbral efectivo (igual no es alerta), los que más faltan primero |
| `GET` / `PUT /inventario/umbral-general` | Ver o cambiar (Administrador) el umbral general; cierra el vigente y deja historial |
| `GET /inventario/historial-umbral?repuesto_id=&solo_general=` | Cambios de umbral |

Cada movimiento responde `alerta: {activa, nueva}`; `nueva` indica que ese
movimiento dejó el repuesto bajo su umbral (para avisar una sola vez; el envío
del aviso lo hará MS1). Todas las operaciones de stock bloquean el repuesto
(`SELECT ... FOR UPDATE`): dos consumos simultáneos nunca dejan stock negativo.
La aprobación de un presupuesto también descuenta lo comprometido por otras
órdenes al decidir si faltan repuestos.

### Pruebas de rollback y consistencia de presupuestos (MS3)

`services/ms3_presupuestos/tests/test_rollback_consistencia.py` (requiere
PostgreSQL migrado; se omite si no hay base):

- **Rollback por operación:** provoca un fallo en mitad de crear, editar,
  crear versión, enviar y decidir (después de que ya se escribió algo) y compara
  la "foto" de la base antes y después con SQL directo: debe ser idéntica, y la
  sesión debe seguir usable.
- **Concurrencia real:** dos o tres peticiones simultáneas con conexiones y
  commits propios (dos decisiones, tres nuevas versiones, editar y enviar a la
  vez): solo una gana, las demás reciben `409`. Corre en un esquema temporal
  `prueba_concurrencia_*` que se migra y se borra al terminar.

Si se quita el `FOR UPDATE` de `RepositorioPresupuestos.obtener_para_actualizar`,
fallan las tres pruebas de concurrencia.

### Aislamiento de la base de MS3

MS3 solo conoce su base (`MS3_DATABASE_URL`). Las órdenes (MS2) y los usuarios
(MS1) se guardan como **referencias lógicas**: un id sin FK que se valida por API.
`services/ms3_presupuestos/aislamiento.py` define las reglas y se comprueba con:

```bash
# Revisa modelo, configuración y la base real (local o Neon). Sale con 1 si hay problemas.
python scripts/verificar_aislamiento_ms3.py
```

Falla si: una FK apunta fuera de MS3, una referencia lógica tiene FK, MS3 comparte
tablas o la misma base con otro servicio, hay tablas ajenas en su base, o está
instalado `dblink`/`postgres_fdw`. Pruebas: `tests/test_ms3_aislamiento.py`
(sin base; además verifica que el código de MS3 no importa `ms1_`/`ms2_`/`ms4_`)
y `services/ms3_presupuestos/tests/test_aislamiento_bd.py` (PostgreSQL).

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

Endpoints de negocio (por la Gateway, con `Authorization: Bearer <token>`):
`POST /api/evidencias` (multipart), `GET /api/evidencias?orden_id=`,
`GET /api/evidencias/{evidencia_id}` y `GET /api/evidencias/{evidencia_id}/descarga`
(URL prefirmada de 5 minutos). Contratos, permisos por rol y ejemplos de uso
(`curl` y `fetch`) en
[`docs/contratos-api-gateway.md`](docs/contratos-api-gateway.md#evidencias-multimedia-ms4).

```bash
# Pruebas de MS4 (las que usan MinIO real se omiten si no está levantado)
python -m pytest tests/test_ms4_*.py tests/test_gateway_evidencias.py -q
```

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
