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

### Capacidad de órdenes por mecánico (MS2)

Un Administrador configura el límite mediante
`PUT /api/ordenes/configuracion/capacidad/mecanicos` con
`{"max_ordenes_activas": 5}` y lo consulta con `GET` sobre la misma ruta. El
límite se aplica al asignar o reasignar: solo cuentan órdenes asignadas que no
están `Entregado` ni `Cancelado`. Las modificaciones conservan auditoría y las
validaciones guardan su resultado. Hay que establecer el límite antes de asignar
órdenes. Si se reduce por debajo de la carga existente, la API informa qué
mecánicos la superan y bloquea nuevos aumentos sin alterar sus órdenes actuales.
Antes del primer uso, aplicar las migraciones de MS2 desde `backend/` con
`alembic -c services/ms2_taller/alembic.ini upgrade head`.

El Administrador configura el cupo de ingresos físicos por jornada en
`/api/ordenes/configuracion/capacidad/ingresos-diarios`. Solo un ingreso físico
nuevo consume cupo; si existe un ingreso abierto se reutiliza, y la salida o
cancelación de la orden no devuelve el cupo de ese día. La jornada usa la zona
IANA definida por `MS2_TIMEZONE` (predeterminada: `America/Santiago`). El límite
diario también debe configurarse antes de recibir el primer vehículo.

Cada servicio tiene su **propia base declarativa**. Es lo que impide que las
tablas de los cuatro dominios terminen mezcladas en una misma migración.

## Puesta en marcha

### Comunicación MS2–MS3 en Vercel

Vercel rechaza bindings circulares. Se conserva MS3 → MS2 como binding y MS2
consulta MS3 por `https://<VERCEL_URL>/ms3`, usando el dominio de ese mismo
despliegue. Omitir `MS2_MS3_URL` en Vercel para activar esta resolución y habilitar
las variables de sistema del proyecto. Una URL explícita sigue teniendo prioridad.
En desarrollo se conserva `http://localhost:8003`; en Kubero se configura el
origen interno de MS3 mediante `MS2_MS3_URL`.

El JWT original siempre se reenvía. Si la URL del despliegue está protegida,
el administrador debe habilitar Protection Bypass for Automation en Vercel:
la plataforma proporciona `VERCEL_AUTOMATION_BYPASS_SECRET`. MS2 lo envía como
`x-vercel-protection-bypass` únicamente a `/ms3` en el dominio de ese despliegue.
No copiar ese secreto al frontend, a Git ni a otros servicios externos; no
desactivar la autenticación JWT ni Deployment Protection. Sin autorización de
plataforma, la integración falla con `503` antes de guardar cambios.

Referencias: [variables de sistema](https://vercel.com/docs/environment-variables/system-environment-variables)
y [protección para automatización](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation).

### Imágenes para Kubero u otro entorno de contenedores

Desde la raíz del repositorio:

```bash
docker build -t sgtm-backend:revision .
docker build -t sgtm-frontend:revision frontend
```

La imagen backend se ejecuta en cinco instancias independientes, con
`SGTM_SERVICIO=gateway`, `ms1`, `ms2`, `ms3` o `ms4`. `PORT` configura el puerto
interno (8000 por defecto). El frontend sirve la SPA y reenvía `/api/*` a la
Gateway; requiere `GATEWAY_UPSTREAM` con su origen HTTP interno, sin ruta ni
barra final. No usar la URL del panel de administración de Kubero como URL API.

Configurar mediante el entorno de cada instancia:

- Cada MS recibe su propio `MSn_DATABASE_URL` con `postgresql+psycopg://` y una
  base independiente. Los cuatro `MSn_JWT_SECRET_KEY` deben coincidir con el
  secreto emisor de MS1 y tener al menos 32 caracteres.
- La Gateway recibe `GATEWAY_MS1_URL` a `GATEWAY_MS4_URL`, con los orígenes
  internos de los servicios, y los orígenes web permitidos en su CORS.
- Las comunicaciones entre dominios requieren `MS2_MS3_URL`, `MS3_MS2_URL`,
  `MS4_MS2_URL` y `MS4_MS3_URL` con los orígenes correspondientes.
- MS4 necesita sus valores `MS4_S3_*`, un bucket privado y credenciales con
  permisos acotados. `MS4_S3_PUBLIC_ENDPOINT` debe ser accesible desde el
  navegador para que funcionen las descargas firmadas.

Las imágenes no incluyen `.env`, entornos virtuales, dependencias locales ni
copias de revisión. El backend corre con un usuario sin privilegios. El arranque
no ejecuta migraciones ni crea usuarios automáticamente.

Desde `backend/`, con las conexiones del entorno configuradas:

```bash
python scripts/verificar_migraciones.py  # Solo lectura, incluye MS1 a MS4.
python scripts/diagnosticar_ms2.py       # Solo lectura, revisa columnas de órdenes.
```

Si hacen falta migraciones, revisar primero el commit desplegado y ejecutar de
forma controlada `python scripts/migrar.py` desde esa misma versión. El migrador
aplica `heads` y vuelve a comprobar las cuatro bases; aborta ante revisiones
desconocidas o si dos servicios apuntan a una misma base. No realiza downgrade,
stamp, seeds ni creación de bases. Una falla puede dejar servicios anteriores
ya migrados: las cuatro bases no comparten una transacción.

`/health/db` solo comprueba conexión mediante `SELECT 1`; un `200` no confirma
que las tablas y columnas estén al día. Antes de entregar una URL a web o móvil,
verificar también login, listado, detalle, permisos y operaciones de órdenes.
`scripts/prueba_integracion_app.py` automatiza consultas con cuentas de prueba
configuradas en `APP_TEST_{CLIENTE,MECANICO,ADMINISTRADOR}_{EMAIL,PASSWORD}`.
No prueba escrituras ni sustituye la integración dentro de la aplicación móvil.

### Desarrollo local

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

#    Con --integracion agrega el catálogo de integración con sus existencias;
#    --verificar solo revisa que el stock cuadre con los movimientos.
python scripts/seed_datos_ms3.py --integracion
python scripts/seed_datos_ms3.py --verificar

# 3. Pruebas de persistencia ORM contra PostgreSQL migrado (se omiten si no hay base)
MS3_ORM_TEST_DATABASE_URL=postgresql+psycopg://taller:taller@localhost:5435/taller_ms3 \
    pytest services/ms3_presupuestos/tests -q
```

### Datos semilla de integración de MS3

Para que el frontend, la app móvil y los otros servicios prueben contra datos
realistas, `services/ms3_presupuestos/datos_integracion.py` define 5
proveedores y 12 repuestos más (además de los 4 de `datos_prueba.py`). Cada
repuesto declara los **movimientos** que explican su stock; la semilla los
registra con los mismos casos de uso que la API, así el stock siempre coincide
con el historial.

| Caso | Repuesto | Stock / umbral |
|---|---|---|
| Stock holgado | Aceite sintético 5W-30 (litro) | 40 / 5 (general) |
| Sin stock (alerta) | Líquido de frenos DOT4 (500 ml) | 0 / 3 — se consumió en la orden 1 |
| Bajo umbral particular (alerta) | Alternador reacondicionado | 1 / 2 |
| Bajo umbral general (alerta) | Kit de embrague | 3 / 5 — 1 consumido en la orden 1 |
| Justo en el umbral (no es alerta) | Bujía de iridio | 5 / 5 |
| Unidades reservadas | Amortiguador delantero | 6, 2 comprometidas para la orden 2 → disponible 4 |
| Corregido con ajuste | Filtro de aire | 12 − 2 = 10 |
| Búsqueda con tildes y eñes | Importadora Ñuble, Bujía de iridio | `q=nuble`, `q=bujia` |
| Proveedor sin repuestos | Neumáticos Cautín | `con_repuestos=false`, se puede eliminar |

- **Idempotente**: proveedores y repuestos se buscan por nombre y cada
  movimiento tiene una `clave_operacion` fija (`semilla-int:<repuesto_id>:<n>`);
  si una carga se cortó, la siguiente la completa.
- Las órdenes son referencias lógicas a MS2: por defecto 1 (en reparación) y 2
  (recibida); se cambian con `--orden-en-reparacion` y `--orden-recibida`.
- Al terminar, el script verifica que el stock de **todos** los repuestos
  coincida con sus movimientos (sale con código 1 si no). Las diferencias con
  los valores de la semilla se muestran como aviso, porque pueden deberse al
  uso real de la app.
- Pruebas: `services/ms3_presupuestos/tests/test_semilla_integracion.py`.

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

**Conexión con la orden** (SCRUM-525): toda escritura (crear, nueva versión,
editar borrador, enviar, decidir) verifica la orden en MS2 con el JWT de quien
llama y lee su `estado_codigo`:

| Situación | Respuesta |
|---|---|
| La orden no existe o no es visible para quien llama (el mecánico solo ve las asignadas) | `404` |
| MS2 no responde | `503` |
| Orden **Entregada** (7) o **Cancelada** (8) | `409`; además se liberan las unidades que la orden aún tenía reservadas (una sola vez) |
| **Primera** decisión con la orden fuera de "Esperando aprobación de presupuesto" (3) | `409`, sin guardar la decisión |
| Decisión de una **modificación** con la orden en curso (4, 5…) | Se registra; la orden no cambia |
| MS2 no informa el estado | MS3 no aplica reglas por estado; MS2 valida al aplicar |

**Versión aprobada bloqueada** (SCRUM-528, migración `0009_ms3`): la versión
aprobada no se edita ni se borra (API `409` y triggers de la base). Para
cambiar lo aprobado se usa `POST /presupuestos/{id}/modificacion`: crea
**obligatoriamente** la versión siguiente (`es_modificacion: true`) como copia
editable de la aprobada (o con los `items` enviados). La aprobada sigue
`vigente: true` hasta que el cliente apruebe la modificación. La base exige
que toda versión creada después de una aprobación sea una modificación y que
no haya dos borradores abiertos. Si el cliente rechaza una modificación, la
siguiente parte de lo aprobado, no de lo rechazado.

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

### Trazabilidad Repuesto–Proveedor/Distribuidor (MS3)

Migración `0007_ms3`. Responde de dónde viene cada repuesto y cada unidad:

- **Tipo de distribuidor**: `tipo_distribuidor` = `oficial` (de la marca) o
  `generico` en proveedores (por defecto `generico`). Filtro
  `GET /proveedores?tipo_distribuidor=oficial` y `proveedor_tipo_distribuidor`
  en cada repuesto.
- **Historial de proveedores** (`historial_proveedor_repuesto`): el alta y cada
  cambio de proveedor de un repuesto, con el administrador y la `observacion`
  del `PATCH /repuestos/{id}`. Lo escribe el modelo (eventos del ORM), así
  ninguna vía de creación se lo salta.
- **Proveedor de cada ingreso** (`movimiento_inventario.proveedor_id`): por
  defecto el proveedor actual del repuesto; se puede indicar otro en el ingreso
  (compra puntual). La base exige proveedor en los ingresos y solo en ellos.
  Las unidades ingresadas siguen asociadas a quien las entregó aunque el
  repuesto cambie de proveedor.
- Un **proveedor que figura en la trazabilidad** (historial o ingresos) no se
  elimina (`409`). Un repuesto que nunca se usó sí se puede eliminar, y su
  historial se va con él.

| Método y ruta | Qué devuelve |
|---|---|
| `GET /repuestos/{id}/trazabilidad` | Proveedor actual, historial de proveedores, ingresos por proveedor (cantidad, unidades, primero y último) y uso por orden (reservado y consumido) |
| `GET /proveedores/{id}/trazabilidad` | Repuestos que abastece (`actual: true`) o abasteció, con las unidades que entregó de cada uno |
| `GET /inventario/movimientos?proveedor_id=` | Ingresos entregados por ese proveedor |

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
| `POST /inventario/disponibilidad` | `{"orden_id"?, "items": [{"repuesto_id", "cantidad"}]}`: valida **antes de usar** si alcanza el stock (no mueve nada). Por repuesto: stock, reservado para la orden, comprometido por otras, disponible, `alcanza` y `faltan` |
| `GET /inventario/ordenes/{orden_id}/disponibilidad` | Lo mismo para lo que falta usar del presupuesto aprobado de la orden (requerido − ya consumido); `409` si no tiene presupuesto aprobado |
| `POST /inventario/ordenes/{orden_id}/reserva` | Reserva lo que falta usar del presupuesto aprobado (todo o nada): `reservado`, `faltantes` y los movimientos. Sirve para reintentar una orden que espera repuestos |
| `POST /inventario/ordenes/{orden_id}/consumos` | `{"clave_operacion", "items": [...]}`: descuenta varios repuestos usados en la orden, todos o ninguno; misma clave → `200`, `repetido: true` |
| `POST /inventario/ordenes/{orden_id}/liberacion` | `{"clave_operacion"}`: libera todo lo reservado por la orden (p. ej. al cancelarla) |

**Validación de disponibilidad** (`services/disponibilidad.py`): para una orden,
disponible = stock − lo comprometido por **otras** órdenes (su propia reserva
cuenta para ella). Las cantidades decimales del presupuesto se redondean hacia
arriba (1,5 litros → 2 unidades). Aprobar un presupuesto usa la misma
validación con los repuestos bloqueados (`FOR UPDATE`, en orden de id) hasta el
commit, para que dos aprobaciones simultáneas no cuenten las mismas unidades.

**Reglas de reserva, descuento y rechazo** (`services/reservas.py`):

- **Reserva**: al aprobar un presupuesto con stock suficiente se reservan
  (compromisos) las unidades que falta usar, en la misma transacción de la
  decisión (`repuestos_reservados` en la respuesta). Si algo no alcanza no se
  reserva nada y la orden espera repuestos. Una modificación aprobada ajusta la
  reserva: reserva la diferencia o libera el sobrante.
- **Descuento**: consumir usa primero lo reservado por la orden y el resto debe
  estar libre; nunca toma lo reservado por otra orden. Varios repuestos se
  descuentan juntos o ninguno.
- **Rechazo**: stock insuficiente responde `409` con `faltantes`
  (`repuesto_id`, `nombre`, `solicitado`, `disponible`, `faltan`) y no aplica nada.
- **Saldo reservado** por orden en orden cronológico: un consumo mayor que lo
  reservado no deja deuda que se coma una reserva posterior.

**Índices de inventario y trazabilidad** (`0008_ms3`): índices compuestos que
entregan el orden de cada listado y el saldo reservado leyendo solo el índice;
el saldo de varios repuestos sale en una consulta. Revisión y mediciones en
[`docs/revision-indices-inventario.md`](docs/revision-indices-inventario.md);
`tests/test_indices_inventario.py` lo verifica con `EXPLAIN`.

**Integración presupuesto aprobado → stock** (`tests/test_integracion_presupuesto_stock.py`,
SCRUM-529): flujo HTTP real MS3 ↔ MS2 con bases separadas (SQLite siempre y
PostgreSQL si están `SCRUM397438_MS2_TEST_URL`/`SCRUM397438_MS3_TEST_URL`):
aprobar con stock deja la orden en reparación y reserva las unidades; sin stock
la deja esperando repuestos sin reservar; al llegar stock la reserva se
completa; usar los repuestos descuenta lo reservado; rechazar cancela sin tocar
el stock; una modificación aprobada ajusta la reserva; y reintentar la
aplicación en MS2 no reserva dos veces.

**Pruebas de presupuestos, inventario, stock y proveedores**
(`services/ms3_presupuestos/tests/test_flujo_presupuesto_inventario_proveedores.py`, SCRUM-526):
el recorrido completo del taller (proveedor → repuesto → presupuesto → envío →
aprobación con reserva → consumo → alerta de stock bajo → reposición →
trazabilidad), aprobar sin stock y reponer, dos órdenes compitiendo por el mismo
repuesto, repuestos/proveedores en uso que no se pueden borrar, cambio de
proveedor sin perder lo entregado, y permisos del cliente.

**Pruebas de límites de stock** (`tests/test_stock_insuficiente_exacto_multiple.py`):
para cada forma de usar stock (consumo, compromiso, ajuste, aprobación, validación
y descuento de varios repuestos), el stock exacto se acepta y deja 0, y una
unidad más responde `409` con `faltan = 1` sin cambiar nada. También el consumo
de varias unidades (un movimiento, varios pasos hasta agotar, reservado + libre,
varios repuestos) y en paralelo: dos descuentos del stock exacto (solo pasa uno)
y descuentos cruzados `[A, B]` / `[B, A]` sin interbloqueo.

Cada movimiento responde `alerta: {activa, nueva}`; `nueva` indica que ese
movimiento dejó el repuesto bajo su umbral (para avisar una sola vez; el envío
del aviso lo hará MS1). Todas las operaciones de stock bloquean el repuesto
(`SELECT ... FOR UPDATE`): dos consumos simultáneos nunca dejan stock negativo.
La aprobación de un presupuesto también descuenta lo comprometido por otras
órdenes al decidir si faltan repuestos.

### Pruebas CRUD de repuestos, proveedores e inventario (MS3)

`services/ms3_presupuestos/tests/test_crud_catalogo_inventario.py` recorre por
HTTP el ciclo completo de cada recurso y revisa la base después de cada paso:

- **Proveedores y repuestos**: crear → leer → listar → modificar → eliminar →
  `404`. Cambios parciales, `umbral_particular: null` vuelve al general,
  reasignar repuestos antes de borrar un proveedor.
- **Inventario**: secuencia de movimientos y stock resultante (físico,
  comprometido por orden, disponible), paginación y filtros. Los movimientos
  no se modifican ni se borran (`405`) y un movimiento rechazado no deja rastro.
- Datos inválidos (`422`, sin guardar nada), ids inválidos y sin token (`401`).

```bash
pytest services/ms3_presupuestos/tests/test_crud_catalogo_inventario.py -v
```

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

### Pruebas integrales de presupuesto, repuestos, proveedores e inventario

Lo que hay que tener levantado para que **ninguna** prueba de MS3 se salte:

| Variable | Para qué |
|---|---|
| `MS3_ORM_TEST_DATABASE_URL` | Base de MS3 migrada (`alembic upgrade head`): ORM, triggers, concurrencia, índices |
| `SCRUM397438_MS2_TEST_URL` / `SCRUM397438_MS3_TEST_URL` | Dos bases locales `verificar_*`: flujo HTTP real MS2 ↔ MS3 en PostgreSQL |
| `INTEGRIDAD_PG_ADMIN_URL` | PostgreSQL local donde crear bases: integridad referencial de los 4 servicios |

```bash
pytest services/ms3_presupuestos/tests \
       tests/test_integracion_presupuesto_stock.py \
       tests/test_decisiones_presupuesto_integracion.py \
       tests/test_decisiones_presupuesto_postgresql.py \
       tests/test_integridad_referencial_servicios.py -q
```

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

### Integridad referencial, índices y mapeos ORM (MS1–MS4)

`tests/test_integridad_referencial_servicios.py` migra cada servicio desde cero
en una base descartable y comprueba que el modelo ORM coincide con las
migraciones, que toda tabla tiene PK, que toda FK tiene índice (o una excepción
documentada), que el ON DELETE es explícito e igual al del modelo, y que no hay
FK entre servicios. Necesita `INTEGRIDAD_PG_ADMIN_URL` (PostgreSQL local);
sin ella se salta. Revisión y hallazgos en
[`docs/revision-integridad-referencial-orm.md`](docs/revision-integridad-referencial-orm.md).

**Mapeos ORM y límites transaccionales** (`tests/test_mapeos_y_transacciones.py`):
`Repuesto.proveedor` e `ItemPresupuesto.repuesto` cargan por lote (`selectin`)
en vez de una consulta por fila; leer el proveedor de un repuesto ya no trae
todos sus repuestos; los movimientos reciben su fecha con `RETURNING` (sin
`refresh`). Antes de cada llamada a MS2 el router cierra la transacción de
lectura con `uow.liberar_conexion()`, para no dejar la conexión
*idle in transaction* mientras MS2 responde (y consulta de vuelta a MS3).

**Consultas por endpoint e índices** (`tests/test_consultas_por_endpoint.py`):
cada endpoint de lectura hace el mismo número de consultas con 2 o con 8 filas
(sin N+1) y no supera su presupuesto medido. La migración `0010_ms3` agrega
`ix_movimiento_inventario_fecha` para el historial general de movimientos
(de ~120 ms a <1 ms con 500.000 movimientos). Mediciones y propuestas en
[`docs/consultas-lentas-y-ajustes-indices.md`](docs/consultas-lentas-y-ajustes-indices.md).

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

La subida solo acepta JPG, PNG, WEBP, MP4 y MOV, verificados por su contenido,
con un máximo de 10 MiB por foto y 100 MiB por video (`MS4_TIPOS_PERMITIDOS`,
`MS4_MAX_BYTES_FOTO`, `MS4_MAX_BYTES_VIDEO`). Para validar la asociación con la
orden, MS4 consulta a MS2 (`MS4_MS2_URL`) y, en evidencias de presupuesto, a MS3
(`MS4_MS3_URL`); ambos deben estar levantados para subir.

MS4 escribe un log por solicitud y por evento de negocio, en formato
`evento=... clave=valor` (nivel con `MS4_LOG_LEVEL`). Para seguir una subida
desde la Gateway basta con filtrar por su `request_id`:

```text
INFO ms4.evidencias evento=evidencia_subida request_id=req-123 evidencia_id=... orden_id=31 tipo_archivo=foto content_type=image/jpeg tamano_bytes=20480 usuario_id=7
WARNING ms4.evidencias evento=subida_rechazada request_id=req-124 motivo=contenido_no_coincide estado_http=415 orden_id=31 usuario_id=7
```

Nunca se registran el JWT, la URL firmada, la clave del objeto, el nombre del
archivo ni su contenido (checklist 5.5).

Para encontrar y limpiar archivos del bucket que quedaron sin fila en la base
(huérfanos), ver `docs/modelo-evidencias.md` § Archivos huérfanos:

```bash
python scripts/limpiar_huerfanos_ms4.py              # solo informa
python scripts/limpiar_huerfanos_ms4.py --eliminar   # borra los huérfanos
```

```bash
# Pruebas de MS4 (las que usan MinIO real se omiten si no está levantado)
python -m pytest tests/test_ms4_*.py tests/test_gateway_evidencias.py tests/test_gateway_rechazos_evidencias.py -q
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
