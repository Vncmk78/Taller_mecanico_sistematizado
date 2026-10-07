# Checklist de seguridad — Evidencia Multimedia (MS4)

Semana 3 · Bastián Liempi · Taller de Integración II (Grupo 10)

Este checklist fija los controles de seguridad que deben cumplir las fotos y
videos de evidencia del SGTM **antes** de construir la subida, el
almacenamiento en MinIO y la consulta de archivos. Cada tarea siguiente de
MS4 se revisa contra esta lista.

## Contexto

- Las evidencias son **fotos o videos** que adjunta el **mecánico** al
  diagnóstico y al presupuesto de una orden de trabajo.
- El **cliente** las revisa para aprobar o rechazar el presupuesto
  (RF18, RF19).
- Regla de negocio: *todo presupuesto debe incluir al menos una foto o video
  como evidencia*.
- Arquitectura: `Web / Móvil → API Gateway → MS4 Evidencia Multimedia`.
  MS4 guarda los **metadatos** en su PostgreSQL y los **archivos** en un
  almacenamiento de objetos (MinIO en desarrollo, compatible con S3).

Cómo leer cada control: **qué** se controla · **por qué** · **cómo se
verifica** · **cuándo** se implementa (tarea del plan).

---

## 1. Recepción del archivo

- [ ] **1.1 Lista blanca de formatos.** Solo se aceptan `image/jpeg`,
  `image/png`, `image/webp`, `video/mp4` y `video/quicktime` (MOV).
  - Por qué: SVG y HTML pueden contener scripts (XSS); ejecutables, ZIP o
    PDF no son evidencia y abren otros vectores de ataque.
  - Verificación: test que sube un `.svg`, un `.html` y un `.exe` y espera
    `415 Unsupported Media Type`.
  - Cuándo: Semana 6 — *Validar tamaño, formato y asociación de archivos*.

- [ ] **1.2 El tipo se valida por el contenido, no por el nombre.** Se leen
  los primeros bytes del archivo (firma o *magic bytes*) y se comparan con el
  formato declarado. No se confía en la extensión ni en el `Content-Type` que
  envía el cliente.
  - Por qué: renombrar `script.html` a `foto.jpg` es trivial.
  - Verificación: test con un HTML renombrado a `.jpg` que debe ser rechazado.
  - Cuándo: Semana 6.

- [ ] **1.3 Tamaño máximo.** Imágenes hasta **10 MB**; videos hasta
  **100 MB** (valores iniciales, ajustables por configuración `MS4_*`).
  Si se supera, se corta la lectura y se responde `413 Payload Too Large`.
  - Por qué: evita agotar disco, memoria y ancho de banda (denegación de
    servicio).
  - Verificación: test con un archivo de 10 MB + 1 byte.
  - Cuándo: Semana 6.

- [x] **1.4 Nombre de almacenamiento generado por el servidor.** El archivo
  se guarda con un UUID (`{uuid}.{ext}`); el nombre original solo se guarda
  como metadato, limpio (sin rutas, sin `../`, máximo 255 caracteres).
  - Por qué: evita *path traversal*, colisiones y nombres con datos
    personales.
  - Verificación: subir `../../etc/passwd.jpg` y comprobar que la clave en
    MinIO es un UUID.
  - Cuándo: Semana 3 — *Implementar base para recepción y almacenamiento de
    metadatos*.
  - ✅ Implementado en `generar_clave_objeto` (UUID + extensión desde el
    content_type) y `nombre_limpio` (basename de lo guardado como metadato);
    verificado en `tests/test_ms4_recepcion.py`. El UUID de la clave es el
    mismo `evidencia_id` de la fila y se valida contra el patrón
    `PATRON_CLAVE_OBJETO`/`es_clave_valida` (convención de claves);
    verificado en `tests/test_ms4_convencion_metadatos.py`. La validación del
    *contenido* (1.2) y del tamaño máximo (1.3) es Semana 6.

- [ ] **1.5 Eliminar metadatos EXIF de las fotos.** Se quitan GPS, modelo
  del teléfono y fecha original antes de guardar.
  - Por qué: la ubicación GPS puede revelar el domicilio del mecánico o del
    cliente.
  - Verificación: subir una foto con GPS y comprobar que la descargada no lo
    tiene.
  - Cuándo: Semana 6.

- [ ] **1.6 Archivo vacío o corrupto se rechaza.** Tamaño 0 o imagen que no
  se puede abrir → `422`.
  - Cuándo: Semana 6.

## 2. Almacenamiento (MinIO / S3)

- [x] **2.1 Bucket privado.** Ninguna política pública (`anonymous`/`public`)
  sobre el bucket de evidencias.
  - Por qué: un bucket público expone todas las fotos de todos los clientes
    a quien adivine la URL.
  - Verificación: `GET` anónimo a un objeto debe responder `403`.
  - Cuándo: Semana 3 — *Configurar MinIO local y credenciales de desarrollo*.
  - ✅ Verificado: `tests/test_ms4_minio_integracion.py` (paso 7: GET anónimo
    al objeto responde `403`) y `scripts/prueba_minio.py`.

- [ ] **2.2 Credenciales fuera del repositorio.** Access key y secret key
  van en `.env` (variables `MS4_*`); en el repo solo existe `.env.example`
  con valores de ejemplo. Nunca se usan las credenciales por defecto
  `minioadmin/minioadmin` fuera del entorno local.
  - Verificación: `git grep` de las claves reales no debe encontrar nada.
  - Cuándo: Semana 3 — *Configurar MinIO local*.

- [ ] **2.3 Usuario de MinIO con mínimo privilegio.** MS4 usa un usuario
  propio con permisos solo sobre su bucket (`get`, `put`, `delete`), no el
  usuario administrador.
  - Cuándo: Semana 3 (local) y Semana 11 (despliegue).

- [x] **2.4 Integridad.** Se calcula y guarda el **SHA-256** de cada archivo
  al subirlo.
  - Por qué: permite detectar archivos alterados y duplicados.
  - Cuándo: Semana 3 — modelo de metadatos.
  - ✅ Implementado: `recibir_evidencia` (flujo A) calcula el SHA-256 al recibir
    y lo guarda en la fila con estado `confirmada` y `confirmada_en`
    (`services/evidencias.py`); verificado en `tests/test_ms4_recepcion.py` y
    `tests/test_ms4_recepcion_minio.py` (sube, descarga y compara el hash).

- [x] **2.5 Convención de claves.** `ordenes/{orden_id}/{uuid}.{ext}`, sin
  datos personales en la ruta (ni patente, ni nombre, ni email).
  - Cuándo: Semana 3.
  - ✅ Implementado en `generar_clave_objeto`: la extensión sale del
    content_type y nunca del nombre enviado; el patrón completo
    (`^ordenes/[1-9][0-9]*/[0-9a-f]{32}\.[a-z0-9]{2,5}$`) está en
    `PATRON_CLAVE_OBJETO` y cualquier clave externa se valida con
    `es_clave_valida`; verificado en `tests/test_ms4_recepcion.py` y
    `tests/test_ms4_convencion_metadatos.py` (incluye que el UUID de la clave
    es el `evidencia_id` de la fila y rechaza `..`, prefijos ajenos, ceros a
    la izquierda y extensiones fuera del patrón).

## 3. Acceso y visibilidad

- [x] **3.1 Quién puede subir.** Solo usuarios con rol **mecánico** o
  **administrador** (validado con el JWT de MS1). Un cliente que intente
  subir recibe `403`.
  - Cuándo: Semana 5 — *Implementar subida y consulta de archivos*.
  - ✅ Implementado: `puede_subir` en `services/permisos.py`; el guard
    `_personal_que_subira` del POST `/evidencias` resuelve el `403` como
    dependencia, **antes** de leer el archivo multipart. Verificado en
    `tests/test_ms4_api_evidencias.py` (201 mecánico/administrador, 403
    cliente sin filas ni objetos, 401 sin token).

- [x] **3.2 Quién puede ver.** El cliente solo ve evidencias de **sus**
  órdenes. La propiedad de la orden se verifica consultando a MS2; nunca se
  confía en un `cliente_id` enviado por el propio cliente.
  - Verificación: test donde el cliente A pide una evidencia del cliente B y
    recibe `404` (no `403`, para no revelar que existe).
  - Cuándo: Semana 3 — *Definir modelo de metadatos, contexto y visibilidad*;
    implementación en Semana 5.
  - ✅ **Implementado.** El filtro por rol vive en `models/evidencia.py` /
    `services/evidencias.py` (`visible_cliente = true AND estado = 'confirmada'
    AND eliminada_en IS NULL` para el cliente, `incluir_eliminadas` para el
    administrador) y **la pertenencia de la orden se valida contra MS2** en
    `services/integracion_ms2.py` (mismo contrato que MS3): MS4 reenvía el MISMO
    JWT a `GET {MS2_URL}/ordenes/{orden_id}`; 200 → sigue, 404/403 → 404 (orden
    ajena en subir/listar; evidencia ajena en detalle/descarga con el **mismo
    body que una inexistente**, sin enumerar), MS2 caído → 503. El administrador
    no consulta MS2 en detalle/descarga (auditoría). Verificado en
    `tests/test_ms4_autorizacion_evidencias.py` (cliente dueño/ajeno, mecánico
    asignado/no asignado, 404 idéntico a UUID inexistente, MS2 caído, unidad de
    `VerificadorOrdenesHttp`) y `tests/test_ms4_api_evidencias.py`.

- [x] **3.3 Descarga con URL prefirmada de corta duración.** MS4 entrega una
  URL firmada de MinIO que expira en **5 minutos**; nunca un enlace
  permanente ni la URL interna del almacenamiento.
  - Verificación: la URL deja de funcionar pasado el tiempo de expiración.
  - Cuándo: Semana 5.
  - Diseño definido en `estudio-urls-firmadas.md` (decisiones D1–D8) e
    implementado en `crear_cliente_s3_publico` / `generar_url_descarga`
    (`services/almacenamiento.py`), probado offline en
    `tests/test_ms4_url_firmada.py` y contra MinIO en
    `tests/test_ms4_minio_integracion.py`.
  - ✅ Endpoint implementado: `GET /evidencias/{id}/descarga` firma con el
    cliente público (`S3_PUBLIC_ENDPOINT`) y `expira_en =
    URL_DESCARGA_TTL_SECONDS` (300 s por defecto); la respuesta es solo
    `{"url", "expira_en"}` y la clave de S3 nunca sale como campo.
    Verificado en `tests/test_ms4_api_evidencias.py` (host público,
    `X-Amz-Expires=300`, sin `clave_objeto`).

- [x] **3.4 Cabeceras de descarga seguras.** `Content-Type` definido por el
  servidor (el validado en 1.2), `X-Content-Type-Options: nosniff` y
  `Content-Disposition` con el nombre limpio.
  - Por qué: impide que el navegador interprete el archivo como otra cosa.
  - Cuándo: Semana 5.
  - Diseño en `estudio-urls-firmadas.md` (§4): `ResponseContentType` y
    `ResponseContentDisposition` viajan **firmados** en la URL
    (`generar_url_descarga`) y `content_disposition_attachment` sanea el nombre
    (ASCII + `filename*` UTF-8). `nosniff` no es forzable por parámetros de S3:
    riesgo aceptado y documentado; la mitigación es `attachment`.
  - ✅ Endpoint implementado: la respuesta de descarga lleva
    `X-Content-Type-Options: nosniff` y `Cache-Control: no-store`.
    Verificado en `tests/test_ms4_api_evidencias.py`.

- [x] **3.5 IDs no adivinables.** Las evidencias se identifican hacia afuera
  con UUID, no con un entero correlativo (`/evidencias/1`, `/2`, …).
  - Cuándo: Semana 3 — modelo de metadatos.
  - ✅ El modelo usa `evidencia_id` UUID como PK (`models/evidencia.py`) y la
    clave pública del objeto reutiliza ese mismo UUID (convención de claves,
    control 2.5): lo que se expone en URLs y logs no es correlativo y no
    filtra volumen. Verificado en `tests/test_ms4_modelo_evidencia.py` y
    `tests/test_ms4_convencion_metadatos.py`. Los endpoints que exponen ese id
    al cliente llegan con la subida/consulta (Semana 5).

## 4. Transporte y API Gateway

- [ ] **4.1 HTTPS en producción** para toda subida y descarga.
  - Cuándo: Semana 11 — despliegue.

- [ ] **4.2 Límite de tamaño en la Gateway.** La Gateway rechaza con `413`
  bodies mayores al máximo de MS4 antes de reenviarlos.
  - Cuándo: Semana 5 — *Integrar operaciones multimedia mediante API
    Gateway*.

- [ ] **4.3 ⚠ Riesgo conocido: la Gateway carga el body completo en
  memoria.** El proxy actual hace `await request.body()` y reenvía el
  contenido de una sola vez. Para fotos no es problema, pero un video de
  100 MB por petición puede agotar la memoria del servidor.
  - Opciones a evaluar: (a) reenvío en *streaming* desde la Gateway a MS4;
    (b) subida directa del cliente a MinIO con **URL prefirmada de subida**
    que entrega MS4 (el archivo no pasa por la Gateway).
  - Cuándo: decidir en Semana 3 (*Estudiar MinIO/S3, multipart y SDK*),
    implementar en Semana 5.
  - ✅ Decidido en `estudio-almacenamiento-objetos.md` (sección 6): fotos
    vía Gateway y MS4; videos con POST prefirmado directo a MinIO y
    confirmación, sin pasar por la Gateway.

- [ ] **4.4 Límite de frecuencia.** Máximo de subidas por usuario y minuto
  (por ejemplo 20), para evitar abuso.
  - Cuándo: Semana 10 — tratamiento de errores de la Gateway.

- [ ] **4.5 Timeouts adecuados.** El timeout de la Gateway hacia MS4 debe
  permitir subir un video del tamaño máximo sin cortar la conexión.
  - Cuándo: Semana 5 y Semana 10.

## 5. Auditoría y ciclo de vida

- [x] **5.1 Registro de cada subida.** Se guarda quién subió (usuario del
  JWT), cuándo, a qué orden o presupuesto pertenece, tamaño, tipo, SHA-256 y
  el `X-Request-ID` que propaga la Gateway.
  - Cuándo: Semana 3 — modelo de metadatos.
  - ✅ **Diseño** definido en `models/evidencia.py`: `autor_usuario_id`,
    `orden_id`/`presupuesto_id`, `tamano_bytes`, `tipo_archivo`, `sha256`,
    `request_id` y `creada_en` (validados en
    `tests/test_ms4_modelo_evidencia.py`). El llenado real desde el JWT y la
    cabecera `X-Request-ID` es la tarea de recepción (Semana 5).

- [ ] **5.2 Evidencia de presupuesto aprobado no se borra.** Una vez que el
  cliente aprobó el presupuesto, sus evidencias quedan inmutables (solo se
  permite marcarlas como anuladas, con registro de quién y por qué).
  - Por qué: la evidencia respalda la decisión del cliente.
  - Cuándo: Semana 6.

- [ ] **5.3 Borrado consistente.** Si se elimina una evidencia permitida, se
  borra el objeto en MinIO **y** el metadato en la base; si falla uno, no
  quedan registros huérfanos.
  - Cuándo: Semana 6.

- [ ] **5.4 Política de retención definida.** Cuánto tiempo se conservan las
  evidencias de órdenes entregadas (propuesta inicial: mientras exista la
  ficha técnica del vehículo).
  - Cuándo: decisión del equipo antes del despliegue (Semana 11).

- [ ] **5.5 Logs sin datos sensibles.** Los logs no incluyen el contenido del
  archivo, tokens JWT ni URLs prefirmadas completas.
  - Cuándo: transversal.

---

## Resumen: control → tarea responsable

| Controles | Tarea | Semana |
|---|---|---|
| 2.1, 2.2, 2.3 | Configurar MinIO local y credenciales de desarrollo | 3 |
| 4.3 (decisión) | Estudiar MinIO/S3, multipart y SDK | 3 |
| 1.4, 2.4, 2.5, 3.2 (diseño), 3.5, 5.1 | Definir modelo de metadatos / base de recepción y almacenamiento | 3 |
| 3.1, 3.2, 3.3, 3.4 | Implementar subida y consulta de archivos en MS4 | 5 |
| 4.2, 4.3, 4.5 | Integrar operaciones multimedia mediante API Gateway | 5 |
| 1.1, 1.2, 1.3, 1.5, 1.6, 5.2, 5.3 | Validar tamaño, formato y asociación de archivos con órdenes | 6 |
| 4.4, 4.5 | Tratamiento de indisponibilidad, timeout y errores en Gateway | 10 |
| 2.3, 4.1, 5.4 | Despliegue de Gateway y servicios en ambiente público | 11 |

## Cómo usar este checklist

1. Antes de cerrar cada tarea de MS4, revisar los controles que le
   corresponden según la tabla.
2. Marcar `[x]` solo cuando exista un **test** o una **verificación
   reproducible** que lo demuestre, y anotar el archivo del test al lado.
3. Si un control se posterga o se descarta, dejar la razón escrita aquí
   mismo.
