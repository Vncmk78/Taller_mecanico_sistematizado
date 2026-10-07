# Modelo de metadatos de evidencias — MS4

Semana 3 · Bastián Liempi · Taller de Integración II (Grupo 10)

Define el modelo `Evidencia` (metadatos) de fotos y videos de orden, las reglas
de visibilidad que usarán las consultas y el flujo de recepción (A) que lo
puebla. Los endpoints HTTP que lo usan están en `routers/evidencias.py`
(subida, listado, detalle y descarga, Semana 5).

El archivo vive en MinIO/S3; en PostgreSQL solo van los **metadatos**. Fuentes:
lámina 04-mer-erd (recuadro "BD MS4"), Sistematización final §4.3, §4.4, §8, y
la tarea *Estudiar MinIO/S3, multipart y SDK*.

## Referencias lógicas a otros servicios (§8)

En MS4 no existen claves foráneas físicas hacia otras bases. Las PKs de los
tres servicios son **enteros seriales** (verificado contra los modelos):

| Columna | Referencia | PK origen |
|---|---|---|
| `orden_id` | Orden de Trabajo (MS2) | `orden_trabajo.orden_id` → `Integer` |
| `presupuesto_id` | Presupuesto (MS3) | `presupuesto.presupuesto_id` → `Integer` |
| `autor_usuario_id` | Usuario (MS1) | `usuario.usuario_id` → `Integer` |
| `eliminada_por_usuario_id` | Usuario (MS1) | `usuario.usuario_id` → `Integer` |

Se guardan como enteros sueltos (marcados REF en el MER) y la integridad se
resuelve por contrato de API, nunca con `ForeignKey`.

## Tabla `evidencia`

| Campo | Tipo | Nulo | Origen | Nota |
|---|---|---|---|---|
| `evidencia_id` | UUID PK | no | MER | Se genera en la app (`uuid4`) |
| `orden_id` | Integer | no | MER | Referencia lógica a MS2, sin FK |
| `presupuesto_id` | Integer | sí | estudio | Solo si contexto = presupuesto |
| `autor_usuario_id` | Integer | no | MER | Referencia lógica a MS1 |
| `contexto` | `str(20)` | no | MER | `diagnostico` / `presupuesto` / `reparacion` / `resultado_final` |
| `tipo_archivo` | `str(10)` | no | MER | `foto` / `video` |
| `visible_cliente` | Boolean | no | MER | Valor por defecto según contexto (ver reglas) |
| `estado` | `str(12)` | no | estudio | `pendiente` / `confirmada` / `anulada` (flujo C) |
| `clave_objeto` | `str(512)` UNIQUE | no | MER | Clave del objeto en MinIO |
| `nombre_original` | `str(255)` | no | estudio | Solo para mostrarlo, nunca para rutas |
| `content_type` | `str(100)` | no | estudio | |
| `tamano_bytes` | `BigInteger` | no | estudio | |
| `sha256` | `CHAR(64)` | sí | estudio | Se llena al confirmar |
| `request_id` | `str(64)` | sí | estudio | Trazabilidad con el Gateway |
| `creada_en` | `timestamptz` | no | MER | `server_default = now()` |
| `confirmada_en` | `timestamptz` | sí | estudio | |
| `eliminada_en` | `timestamptz` | sí | MER | Eliminación lógica |
| `eliminada_por_usuario_id` | Integer | sí | nuevo | Auditoría |

Los enums viven como `StrEnum` en `models/evidencia.py`
(`ContextoEvidencia`, `TipoArchivo`, `EstadoEvidencia`) y se guardan como
strings validados con CHECK, igual que las restricciones por catálogo de MS2.

## Constraints (implementadas como CHECK en `__table_args__`)

1. `contexto` dentro de los 4 valores permitidos.
2. `tipo_archivo` es foto o video.
3. `estado` dentro de los 3 valores permitidos.
4. `tamano_bytes > 0`.
5. `sha256 IS NULL OR length(sha256) = 64`.
6. Si contexto = presupuesto, entonces `presupuesto_id` no es nulo, y al revés.
7. Si contexto = presupuesto, entonces `visible_cliente = true`.
8. Si estado = confirmada, entonces `confirmada_en` y `sha256` no son nulos.
9. `eliminada_en` y `eliminada_por_usuario_id` son los dos nulos o los dos llenos.
10. *Consistencia de estilo MS2*: las referencias lógicas a MS1/MS2/MS3 son
    ids positivos.

La lista de `content_type` permitidos (`image/jpeg`, `image/png`, `image/webp`,
`video/mp4`…) se valida en la aplicación (checklist 1.1 y 1.2), no en la base.

## Índices

- `ix_evidencia_orden_contexto` sobre (`orden_id`, `contexto`): la consulta
  principal de la recepción/carga es "evidencias de la orden X por contexto".
- `ix_evidencia_presupuesto` sobre `presupuesto_id`: soporta RF18 y la regla
  de negocio "todo presupuesto incluye al menos una evidencia".
- `UNIQUE` sobre `clave_objeto` (ya vía `unique=True`).

## Reglas de visibilidad

| Rol | Qué ve | Qué puede hacer |
|---|---|---|
| Cliente | Evidencias de **sus** órdenes (se verifica contra MS2) con `visible_cliente = true`, `estado = confirmada` y `eliminada_en IS NULL` | Solo lectura |
| Mecánico | Todas las confirmadas y no eliminadas de las órdenes que atiende | Subir, cambiar `visible_cliente` (salvo contexto presupuesto), eliminar las propias |
| Administrador | Todo, incluidas las eliminadas (auditoría) | Todo |

El alcance por orden ("sus órdenes" / "las que atiende") lo decide MS2: ver
[Verificación de acceso con MS2](#verificación-de-acceso-con-ms2).

**Valor por defecto de `visible_cliente` según contexto:**

| Contexto | `visible_cliente` por defecto |
|---|---|
| `diagnostico` | `false` (trabajo interno del taller) |
| `reparacion` | `false` |
| `presupuesto` | `true` y no se puede cambiar (regla 7) |
| `resultado_final` | `true` (entrega de la orden) |

**Reglas de negocio**

- Cancelar una orden no borra ni mueve sus evidencias (MER §4.4).
- Una evidencia eliminada lógicamente no cuenta para la regla "todo presupuesto
  debe tener al menos una evidencia".
- Las evidencias anuladas o pendientes nunca se le muestran al cliente.

## Ciclo de estados (flujo C)

```text
             ┌─────────── confirmar ───────────┐
             │                                 ▼
   pendiente ──►  confirmada  ──►  eliminación lógica
             │                                  
             └─────────── anular ──►  anulada
```

- `pendiente` → `confirmada`: exige `confirmada_en` y `sha256` (regla 8); es
  el momento en que el archivo ya está íntegro y se guarda su hash (control 2.4).
- `pendiente` → `anulada`: la evidencia no sirvió (p. ej. foto borrosa) y no se
  muestra al cliente.
- `confirmada`/`anulada` → `eliminada_en`: baja lógica con responsable
  (`eliminada_por_usuario_id`), para auditoría. No borra el archivo de MinIO
  automáticamente: eso lo define la tarea de recepción (checklist 5.3).

## Flujo de recepción (A) — fotos a través de MS4

La recepción (`recibir_evidencia` en `services/evidencias.py`) ejecuta este
orden, diseñado para no dejar residuos:

1. **Valida el content_type** (`image/*` → foto, `video/*` → video) y **calcula
   el SHA-256 y el tamaño** leyendo en bloques de 1 MiB; al terminar deja el
   archivo al inicio.
2. **Archivo de 0 bytes se rechaza** (`EvidenciaInvalidaError`) antes de subir.
3. **Genera el `evidencia_id`** (`uuid4`) y, a partir de él, **la clave**
   `ordenes/{orden_id}/{evidencia_id_hex}.{ext}` — el UUID de la fila y el de la
   clave son el mismo; la extensión sale del content_type, nunca del nombre
   original (checklist 1.4 y 2.5). Ver "Convención de claves de objeto".
4. **Sube a MinIO** con `subir_objeto` (multipart desde 8 MiB, decisión 3 del
   estudio de almacenamiento), incluyendo los `x-amz-meta-*` de soporte
   (evidencia-id, orden-id, sha256, autor-id) — nunca nombre original ni datos
   personales. Si MinIO falla, se propaga y **no se crea ninguna fila**.
5. **Inserta la fila** con estado `confirmada`, `confirmada_en` y `sha256` y
   hace commit. `visible_cliente` solo se escribe si vino en la entrada; si no,
   rige el default por contexto del modelo.
6. **Compensación**: si la base falla, `rollback` y `eliminar_objeto` del objeto
   recién subido (no quedan archivos huérfanos).

Los metadatos que vienen del JWT/cabeceras (autor, `request_id`) no forman
parte del body: los resuelve el endpoint que llama a este servicio.

## Convención de claves de objeto

La clave es la única cadena pública (viaja en URLs y logs), así que sigue un
patrón fijo y autocontenido:

```text
ordenes/{orden_id}/{evidencia_id_hex}.{ext}
```

- **`orden_id`**: entero positivo, sin ceros a la izquierda (el segmento no
  puede empezar con `0`). Nunca es parte de ninguna consulta a la BD.
- **`evidencia_id_hex`**: el id de la evidencia (UUID) en hex (32 caracteres).
  La fila y el objeto comparten el mismo UUID, lo que permite trazabilidad
  certa y, en la limpieza de huérfanos (Semana 6), reconstruir los objetos de
  una orden con un solo prefijo `ordenes/{orden_id}/`.
- **`ext`**: extensión derivada **del content_type** (mapa `_EXT_POR_CONTENT_TYPE`:
  `image/jpeg → jpg`, `image/png → png`, `image/webp → webp`, `image/heic → heic`,
  `image/gif → gif`, `video/mp4 → mp4`, `video/webm → webm`, `video/quicktime → mov`,
  `video/x-msvideo → avi`, `video/mpeg → mpeg`); tipos fuera del mapa van a `.bin`.
  Nunca se copia la extensión ni el nombre que manda el usuario.

Patrón exacto (en `PATRON_CLAVE_OBJETO` de `services/evidencias.py`):

```regex
^ordenes/[1-9][0-9]*/[0-9a-f]{32}\.[a-z0-9]{2,5}$
```

Reglas:

1. **Inmutable**: la clave no cambia nunca tras la recepción (es UNIQUE y es
   el identificador del objeto en MinIO).
2. **Sin datos personales**: no hay nombre del usuario, patente, correo ni
   nombre de archivo del cliente.
3. **Solo ASCII**: `[a-z0-9./]` como mucho; nada de espacios ni caracteres a
   codificar.
4. **Validable desde afuera**: `es_clave_valida(clave)` rechaza cualquier
   desviación (segmentos `..`, prefijos distintos, uuid de otra longitud,
   mayúsculas, extensión fuera de `[a-z0-9]{2,5}`, ceros a la izquierda).

### Metadatos: dónde vive cada dato

El nombre "metadatos" agrupa datos con **destinos distintos**: algunos viven
solo en la BD, otros viajan junto al objeto en S3 (`x-amz-meta-*`, visibles a
quien tenga la clave), y algunos no se guardan en ningún lado (solo en el
`Content-Disposition` de la descarga).

| Dato | BD (`evidencia`) | Objeto (`x-amz-meta-*`) | Nunca se guarda |
|---|---|---|---|
| `evidencia_id` | `evidencia_id` (PK UUID) | `evidencia-id` | |
| `orden_id` | `orden_id` | `orden-id` | |
| `autor_usuario_id` | `autor_usuario_id` | `autor-id` | |
| `sha256` | `sha256` (al confirmar) | `sha256` | |
| `content_type` | `content_type` | — (va en `ContentType` del objeto) | |
| `tamano_bytes` | `tamano_bytes` | | |
| `contexto` | `contexto` | | |
| estado, visibilidad, fechas | columnas del modelo | | |
| `request_id` (Gateway) | `request_id` (normalizado) | | |
| nombre original | `nombre_original` (solo para mostrar) | | **nunca en el objeto** |
| correo, contraseña, datos personales | | | **nunca en ningún lado** |

Regla: el objeto **solo** lleva lo mínimo para soportar/auditar sin abrir la
BD (`evidencia-id`, `orden-id`, `sha256`, `autor-id`); los datos íntegros de la
evidencia viven en la BD, que es la única superficie controlada. `metadatos_objeto`
genera ese dict y se inyecta en `subir_objeto(..., metadatos=...)`.

## Relación con los requisitos funcionales

- **RF18** — *Crear presupuestos con monto y evidencia fotográfica o en
  video*, junto a la regla de negocio *todo presupuesto debe incluir al menos
  una foto o video como evidencia*. Se apoya en `ix_evidencia_presupuesto`: al validar el
  presupuesto se consulta si existe una evidencia `presupuesto_id = X` en estado
  `confirmada` y no eliminada.
- **RF29** — *Adjuntar archivos multimedia (fotografías o video) como evidencia
  en presupuestos y reparaciones.* Se apoya en los contextos `presupuesto` y
  `reparacion`, y en que la evidencia de presupuesto siempre es visible para
  el cliente que lo aprueba (regla 7).

## Verificación de acceso con MS2

MS4 guarda `orden_id` como referencia lógica (§8): no sabe si el cliente es el
dueño del vehículo ni qué mecánico atiende la orden. Para aplicar la visibilidad
de la matriz §4.5, MS4 pregunta a MS2 si la orden es visible para quien llama
llamando a `GET {MS2_URL}/ordenes/{orden_id}` con el **MISMO JWT** del
solicitante (`services/integracion_ms2.py`, mismo contrato que MS3). MS2 aplica
su propio `_filtro_visibilidad` por rol:

```text
Cliente / Mecánico            MS4                              MS2
     │  (su JWT)               │                                │
     │── GET /evidencias ─────►│── GET /ordenes/{id} + Bearer ──►│
     │                         │◄── 200 (visible para él) ───────│
     │◄── 200 / 404 / 503 ─────│◄── 404/403 (ajena o inexistente)│

       200  → la orden es de ese cliente o la atiende el mecánico → MS4 sigue
       404 / 403 → OrdenNoVisible  → MS4 responde 404
       otro código / sin conexión / timeout → ServicioOrdenesNoDisponible → 503
```

Cómo se aplica por endpoint:

- **Subir (`POST`)** y **listar (`GET ?orden_id=`)** exigen la orden visible para
  todos los roles: se valida contra MS2 antes de continuar (`404 "Orden no
  encontrada"` o `503 "El servicio de órdenes no está disponible"`). En la
  subida la validación ocurre **antes** de subir a MinIO: un 404/503 no deja ni
  objeto ni fila.
- **Detalle y descarga**: la evidencia inexistente responde
  `404 "Evidencia no encontrada"`. Para quien no es administrador se valida la
  orden contra MS2 **antes** del filtro de visibilidad: si MS2 responde 404/403,
  la evidencia "no existe" (el mismo 404 que un UUID inexistente, no enumera).
  El **Administrador no consulta MS2** (auditoría: ve todo, incluidas las
  eliminadas) y la decisión termina solo en `es_visible_para`.
- El JWT se reenvía tal como llegó y **nunca** se loguea; MS2 aplica su
  visibilidad por rol, incluida la unión multirol (matriz §3.1).

Implementado en `routers/evidencias.py` (helper `_exigir_orden_accesible`, vía
las dependencias `obtener_token_bearer` y `obtener_verificador_ordenes`) y
probado con un `FakeVerificador` en `tests/test_ms4_autorizacion_evidencias.py`;
`VerificadorOrdenesHttp` se prueba en unidad con `httpx` simulado.

## Endpoints de MS4 (Semana 5)

`routers/evidencias.py` (APIRouter con prefijo `/evidencias`, registrado en
`main.py`). Todos exigen JWT válido (`obtener_principal_actual`).

| Método y ruta | Rol | Respuestas |
|---|---|---|
| `POST /evidencias` (multipart: archivo + `orden_id`, `contexto`, `presupuesto_id`?, `visible_cliente`?) | Mecánico, Administrador | `201 EvidenciaLeida` · `401` · `403` · `404` · `422` · `503` |
| `GET /evidencias?orden_id=` | Cualquier autenticado | `200 [EvidenciaLeida]` · `401` · `404` · `422` · `503` |
| `GET /evidencias/{evidencia_id}` | Cualquier autenticado | `200 EvidenciaLeida` · `401` · `404` · `503` |
| `GET /evidencias/{evidencia_id}/descarga` | Cualquier autenticado | `200 UrlDescarga` · `401` · `404` · `503` |

Detalles:

- `EvidenciaLeida` expone los metadatos de lectura y **nunca** `clave_objeto` ni
  `sha256`; `UrlDescarga` es solo `{"url", "expira_en"}` y la clave de S3 solo
  puede aparecer dentro de la URL firmada.
- Descarga: URL prefirmada del cliente público (`S3_PUBLIC_ENDPOINT`) que
  expira en `URL_DESCARGA_TTL_SECONDS` (por defecto 300 s) y firma
  `response-content-type` + `response-content-disposition`; la respuesta lleva
  `Cache-Control: no-store` y `X-Content-Type-Options: nosniff` (3.3 y 3.4).
- Errores: `403` solo en la subida (el cliente no sube; control 3.1); `404` por
  no enumeración (orden ajena en subir/listar → "Orden no encontrada"; evidencia
  oculta o ajena en detalle/descarga → "Evidencia no encontrada", igual que una
  inexistente); `503` si MS2 no responde o el almacenamiento de objetos falla;
  `422` para las reglas de entrada (formato de archivo, contexto, reglas 6/7 de
  presupuesto). Ver "Verificación de acceso con MS2".

## Pruebas

`tests/test_ms4_modelo_evidencia.py` (SQLite en memoria con `create_all`):
- inserción de una evidencia válida y sus valores por defecto;
- `IntegrityError` para las reglas 1–9 (contexto inválido, tipo inválido,
  tamaño 0, estado inválido, sha256 corto, pareja presupuesto-id incoherente
  en ambas direcciones, presupuesto oculto, confirmada sin sha256, eliminación
  sin responsable, `clave_objeto` duplicada);
- `visible_cliente` por defecto según contexto (4 casos).

`tests/test_ms4_recepcion.py` (SQLite + `FakeS3` en memoria) y
`tests/test_ms4_recepcion_minio.py` (integración real, se salta sin MinIO):
- una foto válida queda confirmada con su sha256 y la clave por convención;
- la clave nunca usa el nombre original (aunque sea `../../x.jpg`);
- `text/plain` y archivos de 0 bytes se rechazan sin fila ni objeto;
- las reglas 6 y 7 se aplican en el schema (`DatosRecepcion`);
- si la base falla se borra el objeto recién subido; si MinIO falla no queda
  ninguna fila;
- `listar_por_orden` filtra por visibilidad según la vista, y
  `presupuesto_tiene_evidencia` implementa la regla de RF18.

`tests/test_ms4_convencion_metadatos.py` (reutiliza `FakeS3`/`sesion` de
`test_ms4_recepcion.py`, ahora registrando `Metadata`):
- la clave cumple `PATRON_CLAVE_OBJETO` y su UUID es el `evidencia_id` de la fila;
- dos recepciones de la misma orden no comparten clave pero sí prefijo;
- `generar_clave_objeto` rechaza ordenes `0`/negativas y acepta `evidencia_id`;
- el objeto guardado lleva `evidencia-id`, `orden-id`, `sha256` y `autor-id`,
  y **nunca** nombre original ni datos personales (todo ASCII);
- `normalizar_request_id` conserva IDs válidos y descarta espacios, caracteres
  raros y valores de más de 64 caracteres; la fila guarda el valor normalizado;
- `es_clave_valida` rechaza `..`, prefijos ajenos, uuid malformado, ceros a la
  izquierda, mayúsculas y extensiones fuera del patrón.

`tests/test_ms4_api_evidencias.py` (TestClient + SQLite en memoria + FakeS3 +
cliente S3 público real que firma offline) cubre los contratos HTTP de los
endpoints de la tabla anterior, con un verificador de MS2 que permite todo
(controles 3.1, 3.3 y 3.4).

`tests/test_ms4_autorizacion_evidencias.py` (TestClient + `FakeVerificador` de
MS2) cubre la verificación contra MS2 por rol: cliente dueño/ajeno en listado
(200 vs 404 "Orden no encontrada"), mecánico asignado/no asignado en subida
(201 vs 404 sin filas ni objetos), cliente que no sube sin llamar a MS2, el
404 idéntico entre evidencia ajena e inexistente, administrador con eliminadas
en el listado y sin consultar MS2 en detalle/descarga, multirol cliente+mecánico
por unión, MS2 caído → 503 en los cuatro endpoints, y la unidad de
`VerificadorOrdenesHttp` con `httpx` simulado (reenvía el JWT, 403/404 →
`OrdenNoVisible`, errores/timeouts → `ServicioOrdenesNoDisponible`).
