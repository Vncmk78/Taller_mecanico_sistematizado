# Estudio: almacenamiento de objetos (MinIO / S3), subida multipart y SDK

Semana 3 · Bastián Liempi · Taller de Integración II (Grupo 10)

Este estudio fija **cómo MS4 (Evidencia Multimedia) va a guardar y entregar
fotos y videos**. Cada sección termina en una decisión que usan las tareas
siguientes: el modelo de metadatos, la estructura inicial de MS4, la subida en
Semana 5 y la validación en Semana 6. Complementa a
`checklist-seguridad-evidencias.md` y `minio-local.md`.

---

## 1. Conceptos de almacenamiento de objetos (S3)

| Concepto | Qué es | En el SGTM |
|---|---|---|
| **Bucket** | Contenedor de objetos con su propia política de acceso. | `evidencias` (privado). |
| **Objeto** | Archivo + metadatos, inmutable: para "editarlo" se sube de nuevo. | Una foto o un video. |
| **Clave (key)** | Nombre único del objeto dentro del bucket. Parece una ruta, pero no hay carpetas reales. | `ordenes/{orden_id}/{uuid}.jpg` |
| **Metadatos del objeto** | `Content-Type`, tamaño, `ETag` y cabeceras `x-amz-meta-*`. | Solo lo técnico; el contexto de negocio va en PostgreSQL de MS4. |
| **ETag** | Identificador del contenido que calcula el servidor. En una subida simple suele ser el MD5; en una **multipart no lo es**. | No sirve como checksum: usamos **SHA-256 propio**. |
| **URL prefirmada** | URL temporal firmada con las credenciales del servicio que permite **una** operación (GET, PUT o POST) sin exponer la clave. | Descargas de 5 minutos; subida directa de videos. |

**Objeto vs. base de datos.** Los archivos no van en PostgreSQL: inflan la
base, vuelven lentos los respaldos y no se pueden servir directamente. El
patrón estándar, que adopta MS4, es:

```
Archivo  ──► MinIO / S3   (bucket "evidencias")
Metadatos ──► PostgreSQL de MS4 (quién, cuándo, a qué orden, tipo, tamaño, SHA-256, clave)
```

**"S3-compatible".** S3 es la API de Amazon para almacenamiento de objetos y se
volvió el estándar de facto. MinIO, Cloudflare R2, Backblaze B2, Garage,
SeaweedFS y otros implementan la misma API. Si el código solo usa operaciones
S3 estándar, **cambiar de proveedor es cambiar el endpoint y las credenciales**.

> **Decisión 1.** MS4 solo usa la API S3 estándar (nada específico de MinIO).
> MinIO es el proveedor de **desarrollo**; el de producción se decide en la
> Semana 11 (despliegue) sin tocar el código.

## 2. Estado de MinIO (2025–2026) y por qué importa

- En 2025 la edición comunitaria de MinIO dejó de publicar binarios e
  imágenes Docker gratuitas, y las imágenes `minio/minio` y `minio/mc`
  dejaron de estar disponibles en Docker Hub. El proyecto comunitario quedó
  en modo mantenimiento.
- En este proyecto se resolvió así (ver `minio-local.md`):
  - **Servidor:** `cgr.dev/chainguard/minio`, fijado por digest (mismo MinIO,
    reconstruido y parchado).
  - **Cliente de inicialización:** `quay.io/minio/mc` con versión exacta.
- **Consecuencia de diseño:** no conviene atar MS4 a MinIO. Por eso la
  decisión 1 (solo API S3) y la decisión 2 (SDK genérico).

## 3. SDK: qué librería usa MS4

| Criterio | `boto3` | `minio` (minio-py) | `aioboto3` |
|---|---|---|---|
| Proveedores | Cualquier S3 | Pensado para MinIO (funciona con S3) | Cualquier S3 |
| Subida multipart automática | Sí (`upload_fileobj` + `TransferConfig`) | Sí (`put_object` con `part_size`) | Sí |
| URL prefirmada GET / PUT | Sí | Sí | Sí |
| POST prefirmado con condiciones | Sí (`generate_presigned_post`) | Sí (`presigned_post_policy`) | Sí |
| Async nativo (FastAPI) | No | No | Sí |
| Documentación y comunidad | Muy amplia (SDK oficial de AWS) | Media | Menor; envoltorio de terceros |
| Dependencia del proveedor | Ninguna | Alta | Ninguna |

**Sobre async.** FastAPI ejecuta los endpoints definidos con `def` (no
`async def`) en un *threadpool*, así que un cliente síncrono como `boto3` no
bloquea el servidor. Si un endpoint es `async def`, las llamadas a `boto3` se
envuelven con `run_in_threadpool`. Para el volumen del taller, esto basta.

**Configuración que ya se validó** en `scripts/prueba_minio.py`:

```python
boto3.client(
    "s3",
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
    region_name=settings.S3_REGION,
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
```

- `signature_version="s3v4"`: firma estándar exigida por MinIO y S3.
- `addressing_style="path"`: URLs `host/bucket/clave`. MinIO lo requiere
  cuando el endpoint es un nombre como `http://minio:9000`, porque el estilo
  *virtual-host* (`bucket.host`) no resuelve en Docker.

> **Decisión 2.** MS4 usa **`boto3`**: es el estándar, no depende de MinIO y
> ya está probado en el repositorio. `minio-py` queda descartado por atarse al
> proveedor; `aioboto3` no aporta lo suficiente para justificar otra
> dependencia.

## 4. Subida multipart

### Qué es

Una subida multipart divide el archivo en **partes** que se suben por
separado (incluso en paralelo) y al final se **ensamblan** en un solo objeto.
El flujo S3 tiene tres llamadas:

1. `CreateMultipartUpload` → devuelve un `UploadId`.
2. `UploadPart` por cada parte (numeradas 1…N) → cada una devuelve su `ETag`.
3. `CompleteMultipartUpload` con la lista de partes y sus `ETag` → el objeto
   aparece en el bucket.
   Si algo falla: `AbortMultipartUpload` libera las partes ya subidas.

### Reglas de S3 que hay que respetar

- Cada parte mide **mínimo 5 MiB**, salvo la última.
- Máximo **10.000 partes** por objeto.
- Una subida simple (`PutObject`) admite hasta 5 GiB; para archivos grandes
  se usa multipart.

Para el SGTM (videos de hasta 100 MB), con partes de 8 MiB un video máximo
son unas 13 partes: muy lejos de los límites.

### Por qué conviene

- **No carga el archivo completo en memoria:** se lee y envía parte por parte.
- **Reintentos baratos:** si se corta la red, se reintenta solo la parte que
  falló.
- **Paralelismo:** varias partes a la vez aceleran la subida de videos.

### Cómo lo hace `boto3`

`upload_fileobj` decide solo si usar multipart según `TransferConfig`:

```python
from boto3.s3.transfer import TransferConfig

config = TransferConfig(
    multipart_threshold=8 * 1024 * 1024,   # desde 8 MiB se usa multipart
    multipart_chunksize=8 * 1024 * 1024,   # partes de 8 MiB (>= 5 MiB)
    max_concurrency=4,
)
cliente.upload_fileobj(archivo, bucket, clave, Config=config,
                       ExtraArgs={"ContentType": "video/mp4"})
```

### Riesgo: subidas abandonadas

Si una subida multipart se inicia y nunca se completa ni se aborta, **sus
partes quedan ocupando espacio** y no aparecen como objeto. Mitigación:

- `boto3` aborta automáticamente cuando `upload_fileobj` falla.
- Además, configurar en el bucket una **regla de ciclo de vida** que aborte
  subidas incompletas después de 1 día (`AbortIncompleteMultipartUpload`).
  Se agrega en la Semana 5, junto con la subida real.

> **Decisión 3.** MS4 sube con `upload_fileobj` y un `TransferConfig` de
> umbral y partes de 8 MiB. Las fotos (≤ 10 MB) casi siempre irán en una sola
> llamada; los videos, en multipart.

## 5. Tres formas de llevar un archivo desde el cliente hasta MinIO

### A. A través de la Gateway y MS4 (proxy)

```
App ──archivo──► Gateway ──archivo──► MS4 ──archivo──► MinIO
```

- ✅ Todo el control en el servidor: MS4 lee los bytes, valida el formato real
  (checklist 1.2), quita el EXIF (1.5) y calcula el SHA-256 (2.4).
- ✅ El cliente no necesita saber nada de S3.
- ❌ El archivo pasa **dos veces** por la red interna y hoy la Gateway hace
  `await request.body()`: **carga el archivo entero en memoria** (riesgo 4.3
  del checklist). Con videos de 100 MB y varias subidas simultáneas, el
  servidor se queda sin memoria.

### B. PUT prefirmado directo a MinIO

```
App ──pide URL──► MS4 ──URL PUT (5 min)──► App ──archivo──► MinIO
```

- ✅ El archivo no pasa por la Gateway ni por MS4.
- ❌ Una URL PUT **no permite limitar el tamaño**: el cliente podría subir
  1 GB con la misma URL.
- ❌ MS4 no ve el contenido durante la subida.

### C. POST prefirmado con condiciones (*POST policy*)

```
App ──pide permiso──► MS4 ──formulario firmado (5 min)──► App ──archivo──► MinIO
App ──confirma──► MS4 ──verifica objeto──► metadatos "confirmada"
```

MS4 genera con `generate_presigned_post` una política firmada que **MinIO
mismo hace cumplir**:

```python
cliente.generate_presigned_post(
    Bucket="evidencias",
    Key=f"ordenes/{orden_id}/{uuid}.mp4",
    Fields={"Content-Type": "video/mp4"},
    Conditions=[
        ["content-length-range", 1, 100 * 1024 * 1024],  # 1 byte a 100 MB
        {"Content-Type": "video/mp4"},
    ],
    ExpiresIn=300,
)
```

- ✅ El archivo no pasa por la Gateway ni por MS4.
- ✅ **El límite de tamaño y el tipo los hace cumplir MinIO**: si no se
  respetan, responde 403.
- ✅ La clave la decide MS4 (UUID), no el cliente (checklist 1.4 y 2.5).
- ❌ Requiere un segundo paso de **confirmación**: MS4 no se entera sola de
  que la subida terminó.
- ❌ MS4 no puede quitar metadatos EXIF (no aplica a videos) ni revisar el
  contenido durante la subida; lo revisa **después**, en la confirmación.

## 6. Decisión: flujo de subida por tipo de archivo

Esta sección resuelve el control **4.3** del checklist.

| Tipo | Tamaño máx. | Flujo | Por qué |
|---|---|---|---|
| **Foto** (JPG, PNG, WEBP) | 10 MB | **A** — vía Gateway y MS4 | Hay que quitar el EXIF (GPS) y validar el formato real: MS4 necesita los bytes. 10 MB en memoria es aceptable. |
| **Video** (MP4, MOV) | 100 MB | **C** — POST prefirmado + confirmación | Evita cargar 100 MB en la Gateway; MinIO hace cumplir tamaño y tipo. |

**Flujo C paso a paso (videos):**

1. El mecánico pide subir un video a una orden: `POST /api/evidencias/subidas`
   con `orden_id`, tipo y tamaño declarado.
2. MS4 valida el rol y la orden, crea el registro de metadatos en estado
   **`pendiente`** y responde el formulario firmado (5 minutos).
3. La app sube el video directo a MinIO con ese formulario.
4. La app confirma: `POST /api/evidencias/{id}/confirmar`.
5. MS4 verifica con `head_object` que el objeto existe y que el tamaño está en
   rango, lee los **primeros bytes** (`Range: bytes=0-63`) para comprobar la
   firma MP4/MOV, calcula el SHA-256 leyendo el objeto por partes y marca la
   evidencia como **`confirmada`**.
6. Si no se confirma a tiempo, un proceso de limpieza borra los registros
   `pendiente` antiguos y sus objetos.

**Para la Gateway** (Semana 5): además, poner un **límite de tamaño de body**
(por ejemplo 12 MB) para que ningún archivo grande entre por el flujo A.

> **Decisión 4.** Fotos por el flujo A; videos por el flujo C con estado
> `pendiente → confirmada`. El riesgo 4.3 queda resuelto por diseño: ningún
> video pasa por la Gateway.

## 7. Qué implica para el modelo de metadatos (siguiente tarea)

Campos que el modelo de MS4 necesita a partir de este estudio:

| Campo | Tipo | Motivo |
|---|---|---|
| `id` | UUID | ID no adivinable hacia afuera (checklist 3.5). |
| `orden_id` | entero | Asociación lógica con la orden de MS2 (sin FK física entre bases). |
| `presupuesto_id` | entero, opcional | Asociación con el presupuesto de MS3 cuando la evidencia lo respalda. |
| `clave_objeto` | texto, único | Ubicación en el bucket (`ordenes/{orden_id}/{uuid}.ext`). |
| `nombre_original` | texto | Solo informativo, limpio (checklist 1.4). |
| `content_type` | texto | Tipo validado por el servidor, no el declarado. |
| `tamano_bytes` | entero | Validación de límites y reportes. |
| `sha256` | texto (64) | Integridad (checklist 2.4). |
| `estado` | enum: `pendiente`, `confirmada`, `anulada` | Flujo C y anulación de evidencias de presupuestos aprobados (5.2). |
| `subido_por` | entero | Usuario del JWT (MS1). |
| `request_id` | texto | Trazabilidad con la Gateway (5.1). |
| `creado_en` / `confirmado_en` | fecha y hora | Auditoría y limpieza de pendientes. |

La **visibilidad** (quién puede ver cada evidencia) se define en esa tarea.

## 8. Resumen de decisiones

| # | Decisión | Impacta en |
|---|---|---|
| 1 | Solo API S3 estándar; MinIO es el proveedor de desarrollo. | Despliegue (Semana 11). |
| 2 | SDK `boto3` con `s3v4` y `addressing_style="path"`. | Estructura de MS4, subida (Semana 5). |
| 3 | `upload_fileobj` + `TransferConfig` de 8 MiB para multipart. | Subida (Semana 5). |
| 4 | Fotos vía MS4; videos con POST prefirmado y confirmación. | Gateway y MS4 (Semana 5), checklist 4.3. |
| 5 | Checksum propio SHA-256; el `ETag` no sirve como checksum en multipart. | Modelo de metadatos (Semana 3). |
| 6 | Regla de ciclo de vida para abortar subidas multipart incompletas. | Configuración de MinIO (Semana 5). |

## 9. Referencias

- Amazon S3 — *Uploading and copying objects using multipart upload*
  (límites de partes y flujo Create/UploadPart/Complete/Abort).
- Amazon S3 — *Browser-based uploads using POST* (POST policy y
  `content-length-range`).
- Boto3 — *File transfer configuration* (`TransferConfig`) y
  `generate_presigned_post`.
- MinIO — documentación de compatibilidad S3 y URLs prefirmadas.
- FastAPI — *Concurrency and async / await* (endpoints `def` en threadpool).
- Repositorio: `backend/scripts/prueba_minio.py` (subida, descarga, SHA-256,
  URL prefirmada y acceso anónimo verificados en local).
