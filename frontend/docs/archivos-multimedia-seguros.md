# Manejo seguro de archivos, imágenes y videos en el navegador (Frontend Web)

Estudio de la subtarea de Semana 6 "Estudiar manejo seguro de archivos, imágenes
y videos en el navegador", aplicado al flujo de **evidencia multimedia** del
portal Cliente y del personal (`frontend/src`), de autoría de Gustavo Rosa.

- Método: inspección de código contra las prácticas de seguridad del navegador
  (carga, validación, renderizado y descarga de binarios) y verificación con la
  suite existente (`npm run lint`, `npm run test`, `npm run build`).
- Sin nuevas dependencias: no se incorporaron librerías de sanitización ni
  procesamiento de imagen/video; el análisis se apoya en lo que el proyecto ya
  usa (React, contrato MS4).

## 1. Modelo de acceso: almacenamiento privado + URLs prefirmadas

El navegador **nunca recibe la clave del objeto** ni una URL permanente del
almacenamiento:

- La respuesta de `GET /api/evidencias` trae solo metadatos
  (`frontend/src/domain/entities/Evidencia.ts`); no incluye URL del archivo.
- Para ver o descargar se pide una URL prefirmada efímera
  (`UrlDescarga.url` + `expiraEn`), **cada vez que se necesita** y sin cachearla
  en stores ni `localStorage`.
- `EvidenceCard` resuelve la URL con `evidenciaService.getDownloadUrl(id)` y la
  descarta al desmontar (flag `active`); si falla, ofrece **Reintentar** en vez
  de dejar una imagen rota.
- El archivo vive en un bucket privado; la expiración limita el impacto de una
  URL filtrada (riesgo aceptado y documentado en el contrato).

**Decisión:** no se usan `URL.createObjectURL` ni blobs en memoria: el archivo
no se descarga completo al cliente para mostrarlo, se sirve directamente desde
el almacenamiento con la URL temporal. Esto evita manejar binarios grandes en el
hilo principal y no requiere `revokeObjectURL`.

## 2. Validación en la subida (`EvidenceUploadForm`)

Doble validación, espejo de los límites del Gateway/MS4:

- **Tipo:** `accept="image/*,video/*"` en el input más
  `esContentTypeEvidenciaPermitido()` (solo `image/*` y `video/*`).
- **Tamaño:** `TAMANO_MAXIMO_EVIDENCIA_BYTES = 12 MiB`, idéntico al límite del
  Gateway para `POST /api/evidencias` (multipart).

La validación es *fail-fast* en cliente, pero la autoridad sigue siendo el
backend (el cliente no decide el resultado final, solo evita viajes inútiles).

## 3. Renderizado seguro de imágenes y videos

- El tipo se determina con `esImagen()` / `esVideo()` a partir de
  `tipoArchivo` y `contentType` (prefijo `image/` / `video/`); no se parsea
  extensiones de nombre de archivo.
- `<img>` y `<video>` son únicos puntos de inserción de medios; **no** se usa
  `dangerouslySetInnerHTML` ni se incrusta HTML del backend. Los nombres de
  archivo (`nombreOriginal`) se pintan como texto → React los escapa (no hay
  inyección de markup vía nombre).
- Miniaturas con `loading="lazy"` (no degradan el render y descargan solo lo
  visible) y `alt={nombreOriginal}`.
- Los videos se reproducen con `<video controls>` nativo sobre la URL
  prefirmada; no se descargan ni se generan extractos/frame thumbnails en el
  cliente.
- El diálogo de vista previa (`EvidencePreviewDialog`) reutiliza la URL ya
  resuelta, cierra con `Escape` y gestiona el foco (`useDialogFocus`), sin crear
  recursos que deban liberarse.

## 4. Descarga del original

`EvidencePreviewDialog` abre la URL prefirmada en una pestaña nueva con
`window.open(url, '_blank', 'noopener,noreferrer')`:

- `noopener`/`noreferrer`: la pestaña destino no obtiene `window.opener`
  (protección contra tabnabbing/reverse tabnabbing).
- La descarga la resuelve el navegador/almacenamiento con la URL temporal; no
  se concatena ni reescribe la URL en el cliente.

## 5. Resumen de controles

| Riesgo | Control implementado | Dónde |
| --- | --- | --- |
| Acceso directo al bucket | Almacenamiento privado + URL prefirmada efímera, pedida bajo demanda | `Evidencia.ts`, `EvidenceCard.tsx` |
| URL filtrada | Expiración corta (`expiraEn`); nunca persistida | `UrlDescarga` |
| Archivo inválido/pesado | Validación de `contentType` y 12 MiB en cliente (backend manda) | `EvidenceUploadForm.tsx` |
| XSS vía nombre de archivo | Solo renderizado de texto (escaping de React) | `EvidenceCard`, `EvidencePreviewDialog` |
| HTML/JS embebido en medios | Sólo `<img>`/`<video>` nativos, sin `dangerouslySetInnerHTML` | componentes de evidencia |
| Tabnabbing al abrir original | `noopener,noreferrer` en `window.open` | `EvidencePreviewDialog.tsx` |
| Memoria/rendimiento | Sin blobs/ObjectURL; miniaturas `lazy`; flag de cancelación al desmontar | `EvidenceCard.tsx` |
| Imagen rota ante error de URL | Estado de fallo + **Reintentar** (no se cachea la URL fallida) | `EvidenceCard.tsx` |

## 6. Verificación

- `npm run lint` → 0 warnings / 0 errors.
- `npm run test` → 81 archivos, 572 pruebas en verde (incluye las de
  evidencia: filtro por contexto, evidencia del presupuesto, reintento de URL).
- `npm run build` → `tsc -b` + Vite sin errores.

**Conclusión:** el flujo cumple las prácticas seguras de manejo de archivos en
el navegador (acceso temporal, validación de tipo/tamaño, renderizado de medios
nativo y aislamiento de pestañas) sin procesar binarios en el cliente. No se
detectaron dependencias pendientes de otros microservicios.
