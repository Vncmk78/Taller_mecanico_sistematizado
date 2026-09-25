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

- [ ] **1.4 Nombre de almacenamiento generado por el servidor.** El archivo
  se guarda con un UUID (`{uuid}.{ext}`); el nombre original solo se guarda
  como metadato, limpio (sin rutas, sin `../`, máximo 255 caracteres).
  - Por qué: evita *path traversal*, colisiones y nombres con datos
    personales.
  - Verificación: subir `../../etc/passwd.jpg` y comprobar que la clave en
    MinIO es un UUID.
  - Cuándo: Semana 3 — *Implementar base para recepción y almacenamiento de
    metadatos*.

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

- [ ] **2.4 Integridad.** Se calcula y guarda el **SHA-256** de cada archivo
  al subirlo.
  - Por qué: permite detectar archivos alterados y duplicados.
  - Cuándo: Semana 3 — modelo de metadatos.
  - Nota: el cálculo y la comparación de SHA-256 quedaron verificados
    (`scripts/prueba_minio.py` y `tests/test_ms4_minio_integracion.py`
    descargan y comprueban que el hash coincide); falta **guardarlo** en los
    metadatos, que es la tarea del modelo de la Semana 3.

- [ ] **2.5 Convención de claves.** `ordenes/{orden_id}/{uuid}.{ext}`, sin
  datos personales en la ruta (ni patente, ni nombre, ni email).
  - Cuándo: Semana 3.

## 3. Acceso y visibilidad

- [ ] **3.1 Quién puede subir.** Solo usuarios con rol **mecánico** o
  **administrador** (validado con el JWT de MS1). Un cliente que intente
  subir recibe `403`.
  - Cuándo: Semana 5 — *Implementar subida y consulta de archivos*.

- [ ] **3.2 Quién puede ver.** El cliente solo ve evidencias de **sus**
  órdenes. La propiedad de la orden se verifica consultando a MS2; nunca se
  confía en un `cliente_id` enviado por el propio cliente.
  - Verificación: test donde el cliente A pide una evidencia del cliente B y
    recibe `404` (no `403`, para no revelar que existe).
  - Cuándo: Semana 3 — *Definir modelo de metadatos, contexto y visibilidad*;
    implementación en Semana 5.

- [ ] **3.3 Descarga con URL prefirmada de corta duración.** MS4 entrega una
  URL firmada de MinIO que expira en **5 minutos**; nunca un enlace
  permanente ni la URL interna del almacenamiento.
  - Verificación: la URL deja de funcionar pasado el tiempo de expiración.
  - Cuándo: Semana 5.

- [ ] **3.4 Cabeceras de descarga seguras.** `Content-Type` definido por el
  servidor (el validado en 1.2), `X-Content-Type-Options: nosniff` y
  `Content-Disposition` con el nombre limpio.
  - Por qué: impide que el navegador interprete el archivo como otra cosa.
  - Cuándo: Semana 5.

- [ ] **3.5 IDs no adivinables.** Las evidencias se identifican hacia afuera
  con UUID, no con un entero correlativo (`/evidencias/1`, `/2`, …).
  - Cuándo: Semana 3 — modelo de metadatos.

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

- [ ] **5.1 Registro de cada subida.** Se guarda quién subió (usuario del
  JWT), cuándo, a qué orden o presupuesto pertenece, tamaño, tipo, SHA-256 y
  el `X-Request-ID` que propaga la Gateway.
  - Cuándo: Semana 3 — modelo de metadatos.

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
