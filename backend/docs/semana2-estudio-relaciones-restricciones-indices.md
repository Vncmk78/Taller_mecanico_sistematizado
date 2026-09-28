# Estudio: relaciones, restricciones e índices en SQLAlchemy / Alembic aplicados al proyecto

Grupo 10 · Taller de Integración II · Semana 2 · Backend SGTM

Nota de estudio de la Semana 2. El objetivo es entender **cómo** SQLAlchemy 2.0 y
Alembic modelan relaciones, restricciones e índices, usando como ejemplo el código
real de los microservicios **MS1 (Autenticación y Usuarios)** y **MS2 (Vehículos y
Órdenes de Trabajo)**. No introduce cambios de esquema: acompaña y explica lo
implementado en las tareas 1 y 2 (migraciones `0001` y `0002` de cada servicio).

Toda referencia a "§" apunta a la Sistematización final del proyecto.

---

## 1. Relaciones ORM

En SQLAlchemy 2.0 una relación se declara con `relationship()` y una anotación
`Mapped[...]`. El par `back_populates` conecta los dos extremos para que al
modificar uno se refleje en el otro dentro de la sesión. Una relación ORM navegable
**solo es posible entre tablas de la misma base**: SQLAlchemy necesita una
`ForeignKey` física para resolver el JOIN.

### 1.1 Cliente 1:N Vehiculo (misma base, MS2)

Es la relación física del proyecto. `Vehiculo.cliente_id` es una `ForeignKey` a
`cliente.cliente_id` con `ON DELETE CASCADE`, y ambos extremos se navegan:

- `Cliente.vehiculos` → lista de vehículos del cliente (lado "uno").
- `Vehiculo.cliente` → cliente dueño (lado "muchos").

Opciones usadas y por qué:

- `cascade="all, delete-orphan"`: al borrar un cliente se borran sus vehículos, y
  un vehículo desasociado de su cliente se elimina. Es comportamiento a nivel ORM.
- `passive_deletes=True`: deja que el borrado en cascada lo ejecute la base con el
  `ON DELETE CASCADE` de la FK, en vez de que el ORM cargue en memoria cada vehículo
  para borrarlo. Sin este flag, el ORM y la base harían el trabajo por duplicado.
- `lazy="selectin"`: al cargar clientes, los vehículos se traen en **una** consulta
  adicional con `IN (...)`, evitando el problema **N+1** (una consulta por cada
  cliente) que aparecería con la carga perezosa por defecto.

### 1.2 Usuario N:M Rol vía UsuarioRol (misma base, MS1)

Un usuario puede tener varios roles y un rol lo tienen varios usuarios (§1.1), así
que la relación es N:M y se resuelve con una **tabla puente** `UsuarioRol` con
**clave primaria compuesta** `(usuario_id, rol_id)`: un usuario no puede tener el
mismo rol dos veces.

Detalle importante de SQLAlchemy: `UsuarioRol` tiene **dos** FK hacia `usuario`
(el titular del rol y `asignado_por_id`, quién lo asignó). Cuando hay más de una FK
a la misma tabla, la relación debe indicar `foreign_keys=[...]` explícitamente para
que SQLAlchemy sepa cuál columna define cada relación; si no, lanza
`AmbiguousForeignKeysError`.

### 1.3 Usuario 1:1 Cliente (cruza de base, MS1 ↔ MS2) — referencia lógica

`Cliente.usuario_id` apunta a un `Usuario` que vive en la base de **MS1**. Como los
microservicios están aislados y **no** existen FK físicas entre sus bases (§8), esta
relación **no** se modela con `relationship()` ni con `ForeignKey`. Se representa con
una columna entera `usuario_id` marcada como **única** (1 usuario ↔ 1 perfil de
cliente) y su integridad se valida por **contrato de API** contra MS1, no por la
base. Es la diferencia central del proyecto: *relación física* vs *referencia
lógica*.

---

## 2. Restricciones (constraints)

Las restricciones viven en la base y protegen la integridad **aunque la aplicación
tenga un error**. Tipos usados en el proyecto:

| Tipo | Para qué | Ejemplo en el proyecto |
|------|----------|------------------------|
| `PrimaryKeyConstraint` | Identidad de fila | `pk_usuario`, `pk_cliente`, PK compuesta `pk_usuario_rol` |
| `UniqueConstraint` | Evitar duplicados | `uq_usuario_correo`, `uq_cliente_usuario_id` |
| `ForeignKeyConstraint` | Integridad referencial + `ON DELETE` | `fk_vehiculo_cliente_id_cliente` (CASCADE), FKs de `usuario_rol` (CASCADE / RESTRICT / SET NULL) |
| `CheckConstraint` | Reglas de dominio documentadas | `ck_vehiculo_patente_no_vacia`, `ck_cliente_usuario_id_positivo` |
| `NOT NULL` | Obligatoriedad | `correo`, `patente`, `marca`, ... |

### 2.1 Acciones `ON DELETE`

En `usuario_rol` se ve el abanico de comportamientos:

- **CASCADE** (`usuario_id`): si se borra el usuario, se borran sus asignaciones.
- **RESTRICT** (`rol_id`): no se puede borrar un rol que todavía está asignado.
- **SET NULL** (`asignado_por_id`): si se borra el administrador que asignó el rol,
  la asignación se conserva pero pierde el "quién".

### 2.2 CHECKs vigentes después de la regularización de Semana 2 (MS2)

- `ck_vehiculo_patente_no_vacia`: la patente obligatoria no puede contener solo
  espacios.
- `ck_cliente_usuario_id_positivo`: la referencia lógica a MS1 debe ser un id > 0.

La migración histórica `0002_ms2` agregó largo de patente, mayúsculas y rangos
para año/kilometraje. Como esas reglas no aparecen en la sistematización final,
`0005_ms2` las retira mediante una migración forward, sin reescribir la migración
ya aplicada. Año y kilometraje permanecen como enteros opcionales.

### 2.3 Convención de nombres

`shared/db.py` define una `naming_convention` en el `MetaData` de cada servicio
(`ck_%(table_name)s_%(constraint_name)s`, `uq_...`, `fk_...`, etc.). Esto hace que
los nombres de las restricciones sean **deterministas**, lo cual es imprescindible
para que Alembic pueda referirse a ellas en `downgrade()` y para que
`op.create_check_constraint("patente_formato", ...)` produzca exactamente
`ck_vehiculo_patente_formato`. Por eso en los modelos se nombran los `CheckConstraint`
**sin** el prefijo: la convención lo antepone y así modelo y migración coinciden.

---

## 3. Índices

Un índice acelera búsquedas y es el mecanismo físico detrás de `UNIQUE`. Tipos:

- **Implícitos**: la PK y toda restricción `UNIQUE` crean su índice automáticamente.
- **Explícitos por columna**: `index=True` en `Vehiculo.cliente_id`
  (`ix_vehiculo_cliente_id`). Se indexan las FK porque se filtran/join-ean seguido
  ("dame los vehículos del cliente X").
- **Único por columna**: `uq_vehiculo_patente` garantiza la unicidad de la patente
  almacenada sin imponer una normalización de mayúsculas que la fuente funcional
  no define. Los espacios exteriores sí se eliminan de forma técnica antes de
  persistir.

Criterio aplicado: se indexa lo que se busca o se une (FK, patente), no cada
columna, para no penalizar las escrituras con índices que nadie usa.

---

## 4. Alembic (migraciones)

### 4.1 Una cadena de migraciones por microservicio

Cada servicio tiene su **propia** base declarativa y su propio `MetaData`
(`crear_base()` en `shared/db.py`), y por lo tanto su **propia** carpeta
`alembic/versions`. Esto es lo que impide que las tablas de los cuatro dominios
terminen mezcladas en una sola migración (§1.2, §8). El `env.py` de cada servicio
importa `Base` y `engine` propios y `target_metadata = Base.metadata`.

### 4.2 Encadenamiento de revisiones

Cada migración declara `revision` y `down_revision`, formando una cadena:

```
MS2:  (base) ──▶ 0001_ms2 ──▶ 0002_ms2 ──▶ 0003_ms2 ──▶ 0004_ms2 ──▶ 0005_ms2
```

Cada revisión apunta a la anterior. `0005_ms2` regulariza las restricciones de
vehículo sin editar destructivamente `0002_ms2`. `upgrade()` aplica los cambios y
`downgrade()` los revierte en orden inverso.

### 4.3 `op.create_*` vs `op.execute`

Las operaciones comunes (tablas, columnas, constraints con nombre, índices por
columna) se hacen con la API de `op`, que además aplica la convención de nombres.
El índice funcional histórico de `0002_ms2` requirió SQL explícito. La restricción
vigente de patente usa operaciones estándar de Alembic.

### 4.4 Verificar la coherencia modelo ↔ base

`alembic check` compara la metadata de los modelos con el estado migrado de la base
y falla si hay diferencias ("upgrade operations detected"). Después de aplicar
`0005_ms2` debe confirmar que la metadata vigente y PostgreSQL coinciden.

---

## 5. Hallazgos y criterios para las próximas semanas

- Mantener la regla física vs lógica: dentro de un servicio, FK reales; entre
  servicios, columnas de referencia + validación por API (nunca FK cruzadas).
- Nombrar constraints/índices sin prefijo en los modelos y dejar que la convención
  los complete, para que las migraciones sean estables y `downgrade()` sea fiable.
- Indexar FK y campos de búsqueda; evitar índices que nadie consulta.
- Normalizar solo cuando no se altere la semántica funcional. En patente se eliminan
  espacios exteriores, sin imponer mayúsculas, regex o largo no documentados.
- Ejecutar `alembic check` y un ciclo up/down antes de subir migraciones nuevas.

---

## Referencias

- Código del proyecto: `backend/services/ms1_auth/models/`,
  `backend/services/ms2_taller/models/`, migraciones `alembic/versions/`.
- `backend/shared/db.py` (base declarativa por servicio y convención de nombres).
- Documentación SQLAlchemy 2.0: ORM Relationships, `relationship()`,
  Naming Conventions, Functional Indexes.
- Documentación Alembic: Operation Reference (`op`), Autogenerate, `alembic check`.
