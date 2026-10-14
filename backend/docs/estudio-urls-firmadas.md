# Estudio: URLs firmadas, claves de objeto y almacenamiento seguro

Semana 5 · Bastián Liempi · Taller de Integración II (Grupo 10)

MS4 (Evidencia Multimedia) guarda las fotos y videos en un bucket **privado**
de MinIO/S3 y los entrega al cliente con una **URL prefirmada** de corta
duración. Este estudio explica cómo se construye esa URL, por qué el endpoint
con el que se firma no puede ser el interno del contenedor, cómo se calculan
las claves de objeto y qué cabeceras de descarga se fuerzan. Cierra con las
decisiones que aplica la tarea *Implementar subida y consulta de archivos*
(Semana 5).

Complementa a `estudio-almacenamiento-objetos.md` (flujos A/B/C y SDK) y a
`checklist-seguridad-evidencias.md` (controles 2.x, 3.3, 3.4 y 3.5). Aquí no
se repiten esos puntos: se profundiza en la firma y la descarga.

---

## 1. Qué es una URL prefirmada (SigV4)

Una **URL prefirmada** (presigned URL) es una URL normal de S3 a la que se le
agregan parámetros de autenticación calculados con las credenciales del
servicio. Quien la recibe puede ejecutar **una sola operación** (`GET`, `PUT`,
`POST`) durante un tiempo limitado, **sin conocer la clave secreta**.

Al pedir `generate_presigned_url("get_object", ...)`, boto3 calcula localmente
una firma **AWS Signature Version 4** y la deja en la *query string*. No hace
ninguna llamada de red: es aritmética sobre el método, la ruta, el host y los
encabezados.

| Parámetro | Qué lleva |
|---|---|
| `X-Amz-Algorithm` | `AWS4-HMAC-SHA256` (la versión de la firma). |
| `X-Amz-Credential` | access key + fecha + región + servicio, p. ej. `ms4-evidencias/20260101/us-east-1/s3/aws4_request`. |
| `X-Amz-Date` | Fecha UTC (`20260101T120000Z`) en que se firmó. |
| `X-Amz-Expires` | Segundos de vigencia desde `X-Amz-Date` (máximo **7 días**). |
| `X-Amz-SignedHeaders` | Encabezados incluidos en la firma (`host` como mínimo). |
| `X-Amz-Signature` | El HMAC-SHA256 final; si un solo carácter cambia, S3 responde `403`. |

La URL es **al portador**: quien la tenga, la usa. Por eso se trata como un
secreto temporal: no se registra completa en logs, no se guarda en la base y no
se comparte fuera del usuario que la pidió.

> **Decisión 1 — Entrega por URL prefirmada `GET`.** MS4 no expone el endpoint
> de MinIO ni sirve los bytes él mismo; entrega una URL firmada con TTL corto.
> El objeto sigue siendo privado y el acceso queda acotado en el tiempo.

---

## 2. El Host está firmado: endpoint interno ≠ endpoint público

SigV4 firma la cabecera `host` (está en `X-Amz-SignedHeaders`). Una URL
firmada contra `http://minio:9000` **solo es válida si el navegador resuelve
`minio`**; contra `http://localhost:9000`, solo desde la máquina donde
`localhost` es ese MinIO. En Docker, MS4 habla con MinIO por el nombre del
servicio (`minio:9000`), pero el cliente (web o móvil) no: para él ese nombre
no existe.

Por eso MS4 necesita **dos endpoints**:

| Endpoint | Para qué | Valor típico |
|---|---|---|
| Interno (`MS4_S3_ENDPOINT`) | Subir, borrar, verificar el bucket. | `http://minio:9000` (Docker) o `http://localhost:9000` (local). |
| Público (`MS4_S3_PUBLIC_ENDPOINT`) | **Firmar** las URLs de descarga. | `https://almacenamiento.ejemplo.cl` en producción. |

Si el público está vacío, se usa el interno: es correcto en desarrollo local,
donde el navegador y MS4 ven el mismo `localhost:9000`, y en producción se
define el dominio real.

> **Decisión 2 — Dos clientes S3.** `crear_cliente_s3` (interno) sube y borra;
> `crear_cliente_s3_publico` (público) solo firma URLs. `MS4_S3_PUBLIC_ENDPOINT`
> es opcional y por defecto cae en `MS4_S3_ENDPOINT`.

---

## 3. Vigencia: 5 minutos, no configurable al alza por el cliente

El control 3.3 fija **5 minutos (300 s)**. Una URL filtrada solo sirve durante
ese lapso y solo para ese objeto. `X-Amz-Expires` lo elige MS4, nunca el
usuario: el cliente no manda el TTL ni el nombre de la clave.

- TTL corto: si se filtra, la ventana de abuso es mínima.
- TTL no tan corto: permite que una descarga de un video razonable termine.
- El valor queda en configuración (`MS4_URL_DESCARGA_TTL_SECONDS`, 30–3600 s)
  para ajustarlo sin tocar código.

La URL **no se persiste** en PostgreSQL (la columna `clave_objeto` sí; la URL
no) ni se cachea. Se genera en el momento de la consulta y se devuelve.

> **Decisión 3 — TTL de 300 s por defecto**, entre 30 y 3600 s, validado en la
> configuración. La URL se genera al pedirla, no se guarda ni se registra
> completa.

---

## 4. Cabeceras de descarga forzadas

El objeto se guardó con su `Content-Type` validado (checklist 1.2), pero eso no
basta al entregarlo: el navegador podría inspeccionar el archivo y adivinar
otro tipo. S3 permite fijar dos **parámetros de respuesta** que van dentro de
la firma, así que viajan protegidos:

| Parámetro | Efecto al descargar |
|---|---|
| `ResponseContentType` | Fuerza el `Content-Type` guardado (el validado), no el que adivine el navegador. |
| `ResponseContentDisposition` | Fuerza `Content-Disposition: attachment; filename=...`, de modo que el archivo **se descargue** y no se renderice en el navegador. |

`X-Content-Type-Options: nosniff` es una cabecera **del servidor que sirve la
respuesta**: no es un parámetro firmable de S3. Como MinIO queda en un origen
distinto (su propio dominio), se documenta como riesgo aceptado; la mitigación
real es `ResponseContentDisposition: attachment`, que impide la renderización
en el dominio de la aplicación.

El nombre de descarga se arma con el nombre original **limpio** (metadato). Para
no romper la cabecera con tildes, comillas o saltos de línea, se envían las dos
formas del RFC 6266 / RFC 5987:

```
attachment; filename="foto-del-taller.jpg"; filename*=UTF-8''foto%20del%20taller.jpg
```

- `filename=`: solo ASCII, sin comillas, `;` ni controles (compatibilidad).
- `filename*=UTF-8''...`: nombre real percent-encoded (conserva tildes y `ñ`).

> **Decisión 4 — `ResponseContentType` + `ResponseContentDisposition` firmados.**
> El tipo y la disposición `attachment` los aplica MinIO al servir el objeto, no
> el cliente. El nombre se sanea con `content_disposition_attachment`.
> `nosniff` no es forzable por S3: riesgo aceptado y documentado (control 3.4).

---

## 5. Claves de objeto: previsibles en estructura, impredecibles en detalle

La clave sigue la convención `ordenes/{orden_id}/{uuid4}.{ext}` (decisión 2.5
del checklist). La extensión sale del `content_type` validado, **nunca** del
nombre que envía el usuario:

```text
ordenes/42/9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e.jpg
```

- `orden_id` en la ruta agrupa las evidencias de una orden (y coincide con el
  índice `ix_evidencia_orden_contexto`), pero por sí solo no revela nada: los
  IDs de orden no son secretos, solo enteros.
- El `uuid4` es lo que hace la clave **no adivinable**: no se puede listar ni
  construir la URL de otra evidencia cambiando un número.
- No hay datos personales en la ruta (ni patente, ni nombre, ni email).

**Clave interna vs. identificador público.** Hacia afuera, una evidencia se
identifica por su `evidencia_id` (UUID, control 3.5), no por la clave ni por un
entero correlativo. La clave es un detalle interno de almacenamiento y no hace
falta exponerla: el endpoint de descarga recibe el `evidencia_id`, busca la fila
y firma la URL de su `clave_objeto`.

> **Decisión 5 — La clave nunca se expone ni la elige el cliente.** El endpoint
> recibe `evidencia_id` (UUID); MS4 resuelve la fila y firma su clave. Un
> `GET /evidencias/1` no existe: sin UUID no hay forma de enumerar.

---

## 6. Almacenamiento seguro: bucket privado y mínimo privilegio

La URL prefirmada solo tiene sentido sobre un **bucket privado** (control 2.1).
MS4 no aplica políticas públicas ni ACLs de lectura anónima, y opera con el
usuario `ms4-evidencias`, cuyos permisos (ver `minio/politica-ms4.json`) son
solo `GetBucketLocation`, `ListBucket`, `GetObject`, `PutObject`,
`DeleteObject` y las operaciones multipart. **No** puede cambiar políticas ni
administrar usuarios.

Puntos que sostienen la seguridad de la descarga:

- **Credenciales solo por entorno** (`MS4_S3_*`); en el repo vive únicamente
  `.env.example`.
- **Firma de corta vida**: aunque la URL se filtre, caduca.
- **Sin persistencia**: la URL no se guarda; si se necesita de nuevo, se firma
  otra.
- **Logs sin la URL**: se registra la clave o el `evidencia_id`, nunca la URL
  completa (control 5.5).
- **Reloj sincronizado**: si el reloj de MS4 atrasa más que el TTL, S3 rechaza
  la firma por fecha inválida. En contenedores con reloj correcto no ocurre.

> **Decisión 6 — Bucket privado + usuario de mínimo privilegio + logs sin URL.**
> La descarga no debilita los controles 2.x; agrega uno temporal (la URL) que
> caduca solo.

---

## 7. URL prefirmada vs. servir el archivo desde MS4

| Criterio | URL prefirmada (elegida) | Streaming por MS4 |
|---|---|---|
| Carga en MS4 | Ninguna: solo firma. | Cada descarga pasa por MS4. |
| Ancho de banda del servicio | No consume. | Consume el del microservicio. |
| Control de cabeceras | Fijas vía parámetros firmados. | Total (puede emitir `nosniff`). |
| Revocación inmediata | No: la URL vive hasta expirar. | Sí: cada petición se autoriza. |
| Complejidad | Baja (una función). | Media (streaming, rangos, timeouts). |

Para el volumen del taller, la URL prefirmada gana: menos código, sin cargar el
microservicio y suficiente control. La falta de revocación inmediata se acota
con el TTL de 5 minutos.

> **Decisión 7 — URL prefirmada.** Servir el archivo desde MS4 (streaming) queda
> descartado por ahora; solo se reconsideraría si hiciera falta revocación
> inmediata.

---

## 8. Decisiones

| # | Decisión |
|---|---|
| D1 | La descarga se entrega con una URL prefirmada `GET`. |
| D2 | Dos clientes S3: interno (subir/borrar) y público (firmar); `MS4_S3_PUBLIC_ENDPOINT` con caída a `MS4_S3_ENDPOINT`. |
| D3 | TTL de 300 s por defecto (30–3600 s), configurable; la URL no se persiste ni se cachea. |
| D4 | `ResponseContentType` y `ResponseContentDisposition` firmados; el nombre se sanea (ASCII + `filename*` UTF-8); `nosniff` no forzable por S3 (riesgo aceptado). |
| D5 | La clave la decide MS4 (`ordenes/{orden_id}/{uuid}.{ext}`); hacia afuera se usa `evidencia_id` (UUID). |
| D6 | Bucket privado y usuario de mínimo privilegio; logs sin la URL completa. |
| D7 | URL prefirmada en vez de streaming desde MS4. |
| D8 | El endpoint `GET /evidencias/{evidencia_id}/descarga` (Semana 5) devuelve `{"url": ..., "expira_en": <segundos>}`; no devuelve la clave ni el endpoint interno. |

---

## 9. Cómo se aplica en el código

| Pieza | Qué hace |
|---|---|
| `config.py` | `S3_PUBLIC_ENDPOINT` y `URL_DESCARGA_TTL_SECONDS` (30–3600). |
| `almacenamiento.crear_cliente_s3_publico` | Cliente boto3 con el endpoint público para firmar. |
| `almacenamiento.generar_url_descarga` | `generate_presigned_url` con tipo, disposición y TTL. |
| `almacenamiento.content_disposition_attachment` | Arma el `Content-Disposition` seguro. |
| `tests/test_ms4_url_firmada.py` | Verifica host, TTL, parámetros firmados y saneo del nombre, sin MinIO (la firma es offline). |
| `scripts/prueba_minio.py` (paso 6) | Prueba real contra MinIO: la URL firmada descarga y el hash coincide. |

---

## 10. Relación con los controles del checklist

| Control | Cómo lo cumple este diseño |
|---|---|
| 2.1 Bucket privado | La URL prefirmada es la única vía; el acceso anónimo da `403`. |
| 3.3 URL de corta duración | TTL 300 s (`URL_DESCARGA_TTL_SECONDS`), sin enlace permanente. |
| 3.4 Cabeceras seguras | `ResponseContentType` y `ResponseContentDisposition` firmados; nombre limpio. |
| 3.5 IDs no adivinables | Se expone `evidencia_id` (UUID); la clave UUID interna no sale. |
| 5.5 Logs sin datos sensibles | No se registra la URL completa. |

La implementación del endpoint y el marcado de los controles 3.3/3.4 es la
tarea *Implementar subida y consulta de archivos* (Semana 5); este estudio solo
fija el diseño.

## Referencias

- AWS — *Authenticating Requests: Using Query Parameters (AWS Signature
  Version 4)* y *GeneratePresignedUrl* (`X-Amz-*`, límite de 7 días).
- Boto3 — `generate_presigned_url` y *ResponseContentType /
  ResponseContentDisposition*.
- RFC 6266 — *Use of the Content-Disposition Header Field*; RFC 5987
  (`filename*`).
- MDN — `Content-Disposition` y `X-Content-Type-Options`.
- Repositorio: `docs/estudio-almacenamiento-objetos.md`,
  `docs/checklist-seguridad-evidencias.md`, `docs/modelo-evidencias.md`,
  `minio/politica-ms4.json`.
