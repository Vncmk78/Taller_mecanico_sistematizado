# Versionado del contrato OpenAPI de la Gateway

**Semana 8 — Publicar una versión estable del contrato OpenAPI para integración.**

El contrato que publica la Gateway en `/openapi.json` es el que consumen el
frontend web y la app móvil de Integración IV. Desde **1.0.0** se considera
**estable**: un cliente que se integró contra 1.0.0 no se rompe hasta 2.0.0.

| | |
|---|---|
| Versión vigente | **2.2.1** |
| Copia congelada | [`docs/openapi/sgtm-gateway-2.2.1.json`](openapi/sgtm-gateway-2.2.1.json) |
| Interactivo | `http://localhost:8000/docs` (Swagger) y `/openapi.json` |
| Dónde se define | `gateway/openapi.py` (`_VERSION`), `gateway/openapi_ms3.py`, `gateway/openapi_ejemplos.py`, `shared/openapi_ordenes.py` |

---

## 1. Cómo lo consumen los otros equipos

- **Sin levantar la Gateway:** usen el archivo congelado. Sirve para generar
  tipos o clientes (`openapi-typescript`, `openapi-generator`, Flutter/Dart,
  etc.) y mocks a partir de los ejemplos.
- **Fijen la versión:** referencien `sgtm-gateway-2.2.1.json` para el comportamiento vigente, no «el último».
  Una versión nueva llega como un archivo nuevo; el anterior no se borra.
- **Solo lo publicado es contrato.** Una ruta que la Gateway reenvía pero no
  aparece en el archivo puede cambiar sin aviso.

## 2. Reglas de versionado (semver)

| Cambio | Versión | Ejemplos |
|---|---|---|
| No cambia el comportamiento | **PATCH** `1.0.x` | Descripciones, ejemplos, documentar un estado de error que el servicio **ya** respondía |
| Agrega sin romper | **MINOR** `1.x.0` | Operación nueva, campo nuevo **opcional** en el body, campo nuevo en una respuesta, valor nuevo de un enum de respuesta |
| Rompe a algún cliente | **MAJOR** `2.0.0` | Quitar o renombrar una ruta o campo, volver obligatorio un campo, cambiar un tipo o formato, cambiar el significado de un estado, exigir autenticación o un rol donde antes no |

Ante la duda entre MINOR y MAJOR, es MAJOR. Un MAJOR se coordina antes con
los equipos web e Integración IV.

## 3. Cómo publicar una versión nueva

Desde `backend/`:

1. Cambia el contrato (`gateway/openapi*.py`, `gateway/contratos/*`).
2. Sube `_VERSION` en `gateway/openapi.py` y `version=` en `gateway/main.py`
   según la tabla anterior.
3. Exporta: `python scripts/exportar_openapi.py` (crea
   `docs/openapi/sgtm-gateway-<version>.json`; el anterior queda como historial).
4. Agrega la entrada en el historial de este documento.
5. Corre `python -m pytest tests/test_gateway_openapi_version_estable.py tests/test_contratos_integracion_iv.py`.

Si cambias el contrato y olvidas los pasos 2 y 3,
`test_archivo_congelado_coincide_con_el_publicado` falla. Para comprobarlo a
mano: `python scripts/exportar_openapi.py --verificar`.

## 4. Historial

### 3.0.0 — Una sola orden activa por vehículo

MAJOR: restringe `POST /api/ordenes`, que antes permitía varias atenciones
activas para el mismo vehículo. Cualquier estado salvo Entregado (7) o
Cancelado (8) es activo. Si existe una orden activa, responde `409` con su
número, sin crear ingreso, orden, historial, outbox ni auditoría de cupo.
El body y la respuesta de éxito no cambian. Se conservan todas las copias
anteriores, incluida 2.2.1.

Decisión aprobada para el Bloque 3. La validación está en el núcleo común y
se respalda con un índice único parcial. La migración
`0013_orden_activa_ms2` aborta y lista los duplicados sin corregirlos.
Antes de desplegar hay que coordinar la versión con web e Integración IV y
diagnosticar la base de destino. Detalles: [orden-activa-por-vehiculo.md](orden-activa-por-vehiculo.md).

Antes de su primera publicación, esta versión incorpora también la Entrega A:
`POST /api/ordenes/{orden_id}/devolucion` (Administrador, body `{}`, 200
idempotente), los campos aditivos y anulables `devuelto_en`/`devuelto_por_id`
en las consultas de órdenes y el cierre atómico del ingreso al entregar.
No hay migración nueva para la salida: usa columnas existentes. No altera
estados oficiales ni repara fechas históricas. La interfaz acordada con web
está en [contrato-web-bloques-3-4.md](contrato-web-bloques-3-4.md).

La misma versión todavía no publicada agrega el backend de la Entrega B:
solicitud de nueva atención del Cliente propietario (`201`/`200` idempotente),
listado y detalle visibles por Cliente/Administrador. Publica la entidad completa,
sus filtros y situaciones sin cambiar estados de órdenes. La tabla y el índice A
se crean mediante `0014_nueva_atencion_ms2`, sin reescribir datos anteriores.
También incorpora el backend C: revisión administrativa inmutable e idempotente,
generación atómica de orden y vínculo (`201`/`200`), y aviso de revisión por
outbox a la bandeja de MS1. No hay migraciones nuevas en C ni cambios al JSON
público de notificaciones. Se agrega un receptor interno autenticado por
servicio, documentado en el acuerdo de coordinación. La integración web C ya está verificada contra servicios reales; la publicación
y activación se confirman con las verificaciones de la entrega. Correo y push tienen adaptadores y cola persistente; SMTP está validado con Mailpit local. Gmail/FCM y el dispositivo móvil requieren configuración externa y validación real.

Antes de publicar 3.0.0 se agregan `leida` y `leida_en` a la bandeja de MS1,
el filtro `solo_no_leidas` y los PATCH de lectura propia (204 sin cuerpo). La
migración `0006_lectura_notificaciones_ms1` agrega columnas, sin borrar avisos
ni cambiar su fecha original. MS1 debe migrarse antes de activar los servicios.

Antes del cierre de 3.0.0 se agregan las cinco operaciones de dispositivos y
canales de notificación, las referencias anulables de contexto y los avisos
transversales de presupuestos/stock. Las alertas de stock no tienen orden ni
vehículo asociados: esos dos campos admiten nulo. MS1 incorpora las migraciones
0007/0008 y MS3 la 0011, con outbox propia. El umbral general debe configurarse
antes de activar alertas, conforme a §4.6 y la decisión del usuario. Particular
prevalece después de ese paso; 0 es válido y la igualdad no dispara aviso.
Detalles de activación y limitaciones: [notificaciones-canales.md](notificaciones-canales.md).

### 2.2.1 — Elementos de `mecanicos_sobre_limite` documentados (D-04)

PATCH: documenta lo que MS2 ya respondía. En `CapacidadMecanicoRespuesta`
(`GET` y `PUT /api/ordenes/configuracion/capacidad/mecanicos`), cada elemento
de `mecanicos_sobre_limite` pasa de un diccionario genérico a
`MecanicoSobreLimite` con `mecanico_id` y `ordenes_activas`, ambos enteros y
obligatorios. El JSON de la respuesta no cambia. Corrige D-04
(`diferencias-contrato-consumo-real.md`).

### 2.2.0 — Perfil Cliente de MS2 para el registro público

Se conserva la copia 2.1.0. MINOR: agrega operaciones sin cambiar las
existentes. `POST /api/clientes/perfil` prepara, de forma idempotente, el perfil
Cliente que MS2 exige para vehículos y órdenes (`201` creado, `200` ya existía,
`409` si existe con otro teléfono, sin sobrescribirlo). `GET /api/clientes/perfil`
lo consulta sin crearlo (`404` si falta). La identidad sale del JWT y el body
no admite `usuario_id` ni roles. `clientes` pasa de alias a prefijo publicado de
MS2 (ya se enrutaba a MS2). Antes de este cambio el perfil solo lo creaba el
script de semilla: un Cliente registrado desde la web o la app recibía `404` en
vehículos. Web e Integración IV deben llamar a `POST /api/clientes/perfil`
después del login de un Cliente y antes de usar vehículos u órdenes.

### 2.1.0 — Modificación de un presupuesto aprobado

MINOR: agrega sin romper.

- Operación nueva `POST /api/presupuestos/{presupuesto_id}/modificacion`
  (body `Modificacion`, `items` opcional): crea la versión siguiente como copia
  editable de la versión aprobada. 409 si no hay versión aprobada o ya hay un
  borrador abierto.
- Campo nuevo `vigente` (bool) en `VersionDetalle`: la versión aprobada que
  manda.
- `PUT …/versiones/{numero}/items` documenta el 409 de la versión aprobada y
  bloqueada, que indica cómo modificarla.

### 2.0.1 — Campos que siempre vienen, publicados como obligatorios

PATCH: no cambia ninguna respuesta, solo documenta lo que ya pasaba. Cierra la
diferencia D-02 de `diferencias-contrato-consumo-real.md`.

| Esquema | Campos que pasan a obligatorios |
|---|---|
| `TokenRespuesta` (login) | `token_type` |
| `BitacoraRespuesta` | `repuestos` (`[]` en una observación) |
| `ResultadoOperacion` (envío y decisión de presupuesto) | `efecto_en_orden`, `repuestos_faltantes`, `repuestos_reservados`, `decision_id`, `aplicacion_en_orden` (pueden valer `null`, pero siempre vienen) |

Los modelos de respuesta declaran `json_schema_serialization_defaults_required=True`
en MS1, MS2, MS3 y en sus copias de `gateway/contratos/`. La Gateway publica como
obligatorios los campos con valor por defecto de esos modelos
(`_exigir_campos_siempre_serializados` en `gateway/openapi.py`), y el OpenAPI de
cada microservicio también.

`backend/requirements.txt` fija `pydantic>=2.12,<2.14`: el JSON Schema de los
`Decimal` cambia entre versiones de pydantic (2.12 y 2.13 publican `pattern`,
2.14 no), y sin ese rango la copia congelada no se podía reproducir en todos los
equipos.

### 2.0.0 — Validación de destinos y órdenes antes de escribir

Definición de seguridad confirmada por Martín el 3 de noviembre de 2026.
Se conservan sin reescribir las copias 1.0.0 y 1.1.0. Las firmas y respuestas de
éxito se mantienen, pero se restringen operaciones antes aceptadas; por eso es
MAJOR. MS2 exige destino activo con rol Mecánico consultando MS1 (`422` si no
cumple). MS3 exige orden existente y asignación al Mecánico al crear presupuesto
(`404` si no corresponde), salvo Administrador. Ambos fallan con `503` sin guardar
cuando no pueden validar con el otro servicio. Los clientes web/móvil deben usar
el JWT original y contemplar esos rechazos; no se agrega un nuevo secreto entre
servicios. Requiere configurar `MS2_MS1_URL` y `MS3_MS2_URL` hacia sus APIs reales.


### 1.1.0 — Integración de historial, avisos y disponibilidad

Se conserva la copia 1.0.0. Este incremento agrega operaciones sin retirar las
existentes: bandeja personal de notificaciones, historial paginado por vehículo,
reserva verificada de repuestos y su aplicación en MS2. La respuesta de entrega
incorpora datos de auditoría. Se conservan los métodos GET y POST cuando ambos
comparten la ruta de disponibilidad de inventario. Los eventos `/interno/*`
siguen fuera de la Gateway.

Los ejemplos para móvil incluyen listado, detalle y finalización de órdenes por
el Mecánico asignado. La validación del contrato y la copia congelada no prueban
que la base del despliegue público esté migrada ni sustituyen una prueba desde
la aplicación de Integración IV.

### 1.0.0 — Semana 8 (primera versión estable)

Base: 59 rutas publicadas (MS1, MS2, MS3, MS4, health e índice). Respecto de
0.1.0 no se quitó ni se renombró nada; solo se completó la documentación de
comportamiento que ya existía (brechas de `contratos-integracion-iv.md` §4):

| ID | Operación | Cambio |
|---|---|---|
| B-01 | `POST /api/auth/login` | Se publican `403` (cuenta sin roles), `422` (body inválido) y `429` (cuenta bloqueada, con cabecera `Retry-After`), con ejemplos tomados de respuestas reales de MS1 |
| B-02 | `GET /api/vehiculos/{vehiculo_id}` | Se publica `422` (identificador no numérico) con su ejemplo real. Se retira un ejemplo de `403` que no correspondía: el endpoint no rechaza por rol, el Mecánico ve los vehículos de sus órdenes asignadas y los demás reciben `404` |
| B-03 | `GET` y `POST /api/ordenes/{orden_id}/bitacora` | Ejemplos de éxito (lista con observación y acción, lista vacía, y body/respuesta del registro) |
| B-04 | `POST /api/ordenes/{orden_id}/cancelacion` | Ejemplos de body, `201` (solicitud creada) y `200` (solicitud repetida) |
| — | `info` | `version` pasa de `0.1.0` a `1.0.0` y la descripción incluye la política de versionado |

### 0.1.0 — Semanas 1 a 7

Contrato en construcción, sin garantía de compatibilidad.
