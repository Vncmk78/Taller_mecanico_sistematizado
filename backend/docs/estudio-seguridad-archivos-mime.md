# Estudio: seguridad de archivos, MIME type y límites de carga

Semana 6 · Bastián Liempi · Taller de Integración II (Grupo 10)

MS4 (Evidencia Multimedia) recibe fotos y videos que sube el mecánico y que
después ve el cliente. Recibir archivos de usuarios es una de las entradas más
riesgosas de una API: el archivo es grande, binario y lo terminan abriendo un
navegador u otro programa. Este estudio explica qué se puede atacar, por qué
el `Content-Type` y la extensión no bastan, cómo se reconoce un formato por sus
primeros bytes y cómo se limita el tamaño en cada capa. Cierra con las
decisiones que aplican las tareas de la Semana 6 y los riesgos que quedan.

Complementa a `checklist-seguridad-evidencias.md` (controles 1.x, 4.2 y 5.5),
a `estudio-almacenamiento-objetos.md` (flujos de subida) y a
`estudio-urls-firmadas.md` (descarga). Aquí no se repiten esos puntos.

---

## 1. Qué puede salir mal al aceptar archivos

| Ataque | Cómo funciona | Qué lo frena en MS4 |
|---|---|---|
| **Script disfrazado de imagen** | Se sube un SVG o un HTML (que pueden traer `<script>`) con nombre `foto.jpg`. Si el navegador lo abre como página, el script corre en el origen de la descarga (XSS). | Lista blanca sin SVG ni HTML (1.1), validación por contenido (1.2) y descarga forzada como `attachment` con el tipo validado (3.4). |
| **Ejecutable o documento como evidencia** | EXE, ZIP o PDF no son evidencia y abren otros vectores (macros, descompresión, visores con fallas). | Lista blanca (1.1): `415`. |
| **Archivo políglota** | Un mismo archivo es válido en dos formatos a la vez, por ejemplo un JPEG que también se puede leer como HTML. | La firma debe ser la del formato declarado y la descarga nunca se sirve como `text/html` (`ResponseContentType` firmado + `attachment`). Riesgo residual en §8. |
| **Denegación de servicio por tamaño** | Subir archivos enormes para llenar disco, memoria o ancho de banda. | Límite en la Gateway (12 MiB, 4.2) y por tipo en MS4 (10 MiB foto, 100 MiB video), cortando la lectura (1.3). |
| **Archivo corrupto o truncado** | Un archivo cortado a la mitad pasa como "foto" pero no se puede ver; el cliente aprueba un presupuesto sin evidencia real. | Revisión estructural por formato (1.6): `422`. |
| **Path traversal por el nombre** | Nombre `../../etc/passwd.jpg` para escribir fuera de la carpeta. | La clave la genera el servidor (`ordenes/{orden}/{uuid}.{ext}`, 1.4 y 2.5); el nombre original es solo un metadato limpio. |
| **Fuga de datos en metadatos** | Fotos con GPS, modelo del teléfono y fecha original (EXIF). | Pendiente (1.5), ver §8. |
| **Fuga por logs** | Registrar el JWT, la URL firmada o el contenido del archivo deja acceso en texto plano a quien lea los logs. | Logs con lista blanca de campos (5.5, `services/registro.py`). |

## 2. MIME type: qué es y por qué no se puede confiar en él

Un **MIME type** (o *media type*, RFC 6838) es la etiqueta `tipo/subtipo` que
dice qué formato tiene un contenido: `image/jpeg`, `video/mp4`, `text/html`.
En una subida multipart, cada parte trae su propio `Content-Type`.

El problema es **quién lo decide**: lo pone el cliente. El navegador lo
deduce, casi siempre, de la **extensión** del archivo, y cualquier cliente
HTTP (curl, Postman, un script) puede mandar el valor que quiera. Renombrar
`script.html` a `foto.jpg` basta para que llegue como `image/jpeg`. Por eso:

- el `Content-Type` recibido es solo una **declaración**, útil para elegir qué
  firma esperar y qué límite aplicar, pero nunca prueba nada;
- la extensión del nombre original **no se usa para nada** (ni para la clave
  ni para decidir el tipo).

Al revés también hay riesgo: al servir un archivo, el navegador puede hacer
**MIME sniffing** (mirar los bytes y "adivinar" el tipo, WHATWG MIME
Sniffing) e ignorar el `Content-Type`. Eso es lo que convierte un archivo
disfrazado en XSS. Las defensas son `X-Content-Type-Options: nosniff` y servir
como descarga (`Content-Disposition: attachment`), ya aplicadas en la Semana 5
(control 3.4).

## 3. Validar por el contenido: firmas o *magic bytes*

Casi todos los formatos binarios empiezan con una secuencia fija de bytes, la
**firma** o *magic bytes*. Leer los primeros bytes del archivo dice qué es en
realidad, sin importar el nombre ni el `Content-Type`.

| Formato | Firma (hex) | Dónde | Detalle |
|---|---|---|---|
| JPEG | `FF D8 FF` | byte 0 | SOI (*Start Of Image*) seguido del primer marcador. |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | byte 0 | `\x89PNG\r\n\x1a\n`; los bytes de control detectan transferencias que alteran saltos de línea. |
| WEBP | `52 49 46 46` … `57 45 42 50` | bytes 0 y 8 | Contenedor RIFF (`RIFF` + tamaño + `WEBP`). Los 4 bytes del medio son el tamaño, por eso la firma no es contigua. |
| MP4 | `?? ?? ?? ?? 66 74 79 70` | byte 4 | Caja `ftyp` de ISO BMFF; los bytes 8–11 son la marca (`isom`, `mp41`, `mp42`, `avc1`…). |
| MOV | `66 74 79 70 71 74 20 20` | byte 4 | `ftyp` con marca `qt  `. MOV antiguos empiezan directo con `moov`, `mdat`, `wide`, `free`… |

Puntos finos que se resolvieron en el código (`detectar_formato`):

- **HEIC/HEIF/AVIF también empiezan con `ftyp`**: son imágenes del mismo
  contenedor que el MP4. Se distinguen por la marca (`heic`, `mif1`, `avif`…)
  y se rechazan: no están en la lista blanca.
- **MP4 y MOV son intercambiables**: comparten la estructura ISO BMFF y los
  navegadores los etiquetan de forma inconsistente (un `.mov` de iPhone puede
  llegar como `video/mp4`). Se aceptan cruzados y se guarda el tipo detectado.
- **Basta con 16 bytes** para reconocer los cinco formatos.

Qué **no** garantiza la firma: que el resto del archivo sea sano. Un archivo
puede tener una firma JPEG perfecta y basura (o un script) después. Por eso la
firma se complementa con la revisión estructural (§4) y con una descarga que
nunca deja al navegador interpretar el archivo (3.4).

## 4. Validación estructural: ¿el archivo está completo?

Sin agregar librerías de imágenes, se puede revisar que la **estructura** del
formato esté completa (control 1.6):

| Formato | Regla | Detecta |
|---|---|---|
| JPEG | Debe aparecer el marcador EOI `FF D9` después de la cabecera. | Fotos cortadas en la subida. Se acepta que haya datos después del EOI: algunas cámaras agregan información ahí. |
| PNG | Debe aparecer el chunk `IEND` (con su CRC fijo `AE 42 60 82`). | PNG truncados. |
| WEBP | El tamaño declarado en la cabecera RIFF no puede superar el tamaño real. | WEBP truncados. |
| MP4 / MOV | Todas las cajas de primer nivel deben caber en el archivo (incluye cajas de 64 bits y la caja final "hasta el final", tamaño 0) y debe existir `moov`. | Videos cortados y videos sin la caja que describe las pistas (no se pueden reproducir). |

La búsqueda de `FF D9` e `IEND` se hace en bloques de 1 MiB conservando el
final del bloque anterior, para no perder una firma partida entre dos bloques
y sin cargar el archivo completo en memoria.

Lo que esta revisión **no** hace es decodificar los píxeles o los fotogramas.
Una imagen con estructura completa pero datos internos alterados pasa. Para
eso habría que abrirla con una librería (Pillow, ffprobe), lo que agrega
dependencias y superficie de ataque (los decodificadores son justamente donde
aparecen fallas). Se dejó para cuando se implemente la limpieza de EXIF (1.5),
que necesita abrir la imagen de todos modos.

## 5. Límites de carga por capas

Un solo límite no basta: cada capa tiene que poder defenderse sola.

```text
Cliente ──► API Gateway ──────────────► MS4 ───────────────────────► MinIO
            413 si body > 12 MiB         413 si foto > 10 MiB          (solo lo
            (antes de leerlo o llamar    o video > 100 MiB,             que pasó
            a MS4; corta el streaming    cortando la lectura apenas     todas las
            si no hay Content-Length)    se supera                      validaciones)
```

| Capa | Límite | Por qué ese valor |
|---|---|---|
| Gateway, prefijos JSON | 1 MiB | Ningún body JSON legítimo se acerca a eso. |
| Gateway, `evidencias` | 12 MiB | Una foto de hasta 10 MB más el margen del multipart (cabeceras de cada parte, campos del formulario). |
| MS4, fotos | 10 MiB (`MS4_MAX_BYTES_FOTO`) | Una foto de teléfono actual pesa entre 2 y 8 MB; 10 MiB deja margen sin abrir la puerta a abusos. |
| MS4, videos | 100 MiB (`MS4_MAX_BYTES_VIDEO`) | Clips cortos de evidencia. Por la Gateway hoy no pasa más de 12 MiB: los videos grandes irán por subida directa a MinIO (flujo C, pendiente). |

Detalles de implementación que importan:

- **El límite se aplica por tipo**, no uno solo para todo: así una foto no
  puede pesar lo que un video.
- **La lectura se corta**: `calcular_sha256_y_tamano(maximo=...)` deja de leer
  y de calcular el hash apenas se pasa del límite, en vez de procesar el
  archivo completo para después rechazarlo.
- **Todo se valida antes de subir a MinIO**: un rechazo nunca deja objetos ni
  filas, así no hace falta limpiar nada.
- **El servidor de aplicación también acota**: Starlette guarda en disco
  temporal las partes grandes del multipart en vez de mantenerlas en memoria,
  y nunca recibe más de lo que dejó pasar la Gateway.
- **Los límites se configuran por entorno**, pero la lista blanca solo admite
  formatos que MS4 sabe verificar (`FORMATOS_SOPORTADOS`): nadie puede
  habilitar por configuración un tipo sin firma conocida.

## 6. Qué código HTTP corresponde a cada rechazo

| Código | Cuándo | Por qué ese y no otro |
|---|---|---|
| `400 Bad Request` | El archivo recibido no se pudo leer. | La petición está rota en sí, no es un problema de formato ni de reglas. |
| `413 Content Too Large` | El archivo supera el límite de su tipo, o el body el de la Gateway. | RFC 9110 §15.5.14: el contenido es más grande de lo que el servidor acepta. |
| `415 Unsupported Media Type` | Formato fuera de la lista blanca, o bytes que no corresponden al tipo declarado. | RFC 9110 §15.5.16: el formato del contenido no es soportado por el recurso. |
| `422 Unprocessable Content` | Archivo vacío o dañado, presupuesto de otra orden, formulario inválido. | El formato es correcto pero el contenido no se puede procesar según las reglas. |
| `409 Conflict` | La orden está entregada o cancelada. | El estado del recurso (la orden) no admite la operación. |

El orden en que se evalúan también es una decisión de seguridad: primero
autenticación y rol, después la orden y el presupuesto, y recién al final el
archivo. Así un archivo inválido no permite averiguar si una orden existe
(no enumeración): una orden inexistente responde `404` aunque el archivo sea
un HTML.

## 7. Decisiones

| # | Decisión | Alternativa descartada |
|---|---|---|
| D1 | Lista blanca cerrada de 5 formatos (JPG, PNG, WEBP, MP4, MOV). | Lista negra (SVG, HTML, EXE…): siempre falta algún formato peligroso. |
| D2 | El tipo se decide por los *magic bytes*; el `Content-Type` solo dice qué firma esperar. | Confiar en el `Content-Type` o la extensión: se falsifican trivialmente. |
| D3 | Se guarda y se firma la descarga con el tipo **detectado**. | Guardar el declarado: la descarga podría servir un tipo que no es el real. |
| D4 | MP4 y MOV se aceptan cruzados. | Exigir coincidencia exacta: rechazaría videos reales de iPhone. |
| D5 | Revisión estructural propia, sin librerías de imágenes. | Pillow/ffprobe: más dependencias y decodificadores como superficie de ataque; se evalúa con 1.5. |
| D6 | Límite por tipo, configurable, con lectura cortada. | Un límite único: o es chico para videos o es grande para fotos. |
| D7 | Todas las validaciones antes de subir a MinIO. | Subir y validar después: obliga a limpiar en cada rechazo. |
| D8 | GIF y HEIC fuera de la lista. | GIF no aporta como evidencia y HEIC no lo abren todos los navegadores del cliente. |

## 8. Riesgos residuales y próximos pasos

| Riesgo | Estado | Próximo paso |
|---|---|---|
| Metadatos EXIF con GPS en las fotos (1.5). | Pendiente. | Quitar EXIF al recibir (requiere decodificar la imagen; evaluar Pillow con límites de dimensiones para evitar *decompression bombs*). |
| Contenido interno alterado con estructura válida. | Aceptado. | Se cubre al decodificar en 1.5; mientras tanto la descarga forzada (3.4) evita que se ejecute. |
| Malware dentro de un archivo válido. | Fuera de alcance. | Antivirus (por ejemplo ClamAV) si el despliegue lo exige. |
| Videos grandes por la Gateway (tope 12 MiB). | Acotado. | Flujo C: subida directa a MinIO con POST prefirmado y validación posterior. |
| El frontend acepta `image/*,video/*`. | El backend rechaza igual (415). | Restringir `accept` a los 5 formatos para mejor experiencia. |
| Abuso por cantidad de subidas. | Pendiente (4.4). | Límite de frecuencia en la Gateway (Semana 10). |

## 9. Cómo se aplica en el código

| Archivo | Qué hace |
|---|---|
| `services/ms4_evidencias/config.py` | `FORMATOS_SOPORTADOS`, `MS4_TIPOS_PERMITIDOS`, `MS4_MAX_BYTES_FOTO`, `MS4_MAX_BYTES_VIDEO`. |
| `services/ms4_evidencias/services/validacion_archivos.py` | `PoliticaArchivos` (lista blanca y límites), `detectar_formato`, `validar_contenido` y las excepciones de dominio (415/413/422/400). |
| `services/ms4_evidencias/services/almacenamiento.py` | `calcular_sha256_y_tamano(maximo=...)`: lectura en bloques cortada al superar el límite. |
| `services/ms4_evidencias/services/evidencias.py` | `recibir_evidencia`: aplica todo antes de subir y compensa si la base falla. |
| `services/ms4_evidencias/routers/evidencias.py` | Traduce cada excepción a su código HTTP y registra el motivo en el log. |
| `gateway/config.py` y `gateway/routers/proxy.py` | Límite de body por prefijo (4.2). |

## 10. Relación con los controles del checklist

| Control | Dónde se discute aquí | Estado |
|---|---|---|
| 1.1 Lista blanca | §1, §7 (D1, D8) | ✅ |
| 1.2 Tipo por contenido | §2, §3, §7 (D2–D4) | ✅ |
| 1.3 Tamaño máximo | §5, §7 (D6) | ✅ |
| 1.5 EXIF | §8 | Pendiente |
| 1.6 Vacío o corrupto | §4, §7 (D5) | ✅ (estructura, sin decodificar) |
| 3.4 Cabeceras de descarga | §2 | ✅ (Semana 5) |
| 4.2 Límite en la Gateway | §5 | ✅ (Semana 5) |
| 5.5 Logs sin datos sensibles | §1 | ✅ |

## Referencias

- OWASP — File Upload Cheat Sheet:
  <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>
- RFC 9110 — HTTP Semantics (413, 415, 422): <https://www.rfc-editor.org/rfc/rfc9110>
- RFC 6838 — Media Type Specifications and Registration Procedures:
  <https://www.rfc-editor.org/rfc/rfc6838>
- WHATWG — MIME Sniffing Standard: <https://mimesniff.spec.whatwg.org/>
- W3C — Portable Network Graphics (PNG) Specification: <https://www.w3.org/TR/png/>
- Google — WebP Container Specification (RIFF):
  <https://developers.google.com/speed/webp/docs/riff_container>
- ISO/IEC 14496-12 — ISO Base Media File Format (estructura de cajas de MP4/MOV).
