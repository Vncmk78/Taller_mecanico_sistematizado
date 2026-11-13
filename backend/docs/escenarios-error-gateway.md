# Escenarios de error y comportamiento esperado (Gateway y servicio multimedia)

Semana 10 · Bastián Liempi · Taller de Integración II (Grupo 10)
Tareas: SCRUM-579, 580, 581, 582, 583, 584 y 585.

Este documento es la referencia única de **qué responde el sistema cuando algo
falla**: qué ve el cliente (web o app móvil), qué cabeceras recibe, qué queda en
los logs y cómo reproducir cada caso. Cada fila está cubierta por una prueba
automática (columna "Prueba").

## 1. Reglas generales

1. **Formato común de los errores que genera la Gateway**:

   ```json
   {
     "detail": "El servicio tardó demasiado en responder. Intente más tarde.",
     "error": {
       "codigo": "TIEMPO_AGOTADO",
       "estado": 504,
       "ruta": "/api/vehiculos",
       "request_id": "3f6c1e0a-6a43-4f63-9a3e-2b1a9f0f7c11"
     }
   }
   ```

   `detail` es el mensaje para mostrar; `error.codigo` es para el código del
   cliente; `error.request_id` es la referencia para soporte.
2. **Errores de un microservicio con JSON pasan tal cual** (`{"detail": ...}`
   con su estado). No se reescriben: web y móvil dependen de ese contrato.
3. **Toda respuesta** (éxito o error, de la Gateway o de un microservicio) trae
   la cabecera `X-Request-ID`. La web la muestra como "Referencia: …".
4. Los `502`, `503` y `504` de la Gateway traen `Retry-After` (segundos,
   `GATEWAY_RETRY_AFTER_SECONDS`, 5 por defecto) y todos sus errores
   `Cache-Control: no-store`.
5. **Nunca** llegan al cliente: URLs internas, nombres de bucket o claves de
   objeto, trazas, SQL ni el body inválido que mandó un servicio.
6. La Gateway **no reintenta** peticiones ya enviadas (solo un reintento al
   conectar). Para escrituras, un `502/503/504` significa "resultado incierto":
   el cliente debe verificar con un `GET` antes de repetir
   (`esResultadoIncierto` en `frontend/src/infrastructure/api/errors.ts`).

## 2. Gateway → microservicio

| # | Escenario | Estado | `error.codigo` | Mensaje (`detail`) | Log de la Gateway | Prueba |
|---|---|---|---|---|---|---|
| G1 | Servicio caído (conexión rechazada o no conecta en 3 s) | 502 | `MICROSERVICIO_INALCANZABLE` | El servicio no está disponible. Intente más tarde. | `Fallo de red hacia el microservicio ms2_taller: ConnectError (timeout_lectura=15.0s, request_id=…)` | `test_gateway_simulacion_fallos.py::test_servicio_caido_responde_502_controlado` |
| G2 | Servicio lento (supera el timeout de lectura/escritura) | 504 | `TIEMPO_AGOTADO` | El servicio tardó demasiado en responder. Intente más tarde. | `… ReadTimeout (timeout_lectura=<s>s, request_id=…)` | `…::test_servicio_lento_corta_por_timeout_y_responde_504` |
| G3 | Pool de conexiones de la Gateway agotado | 503 | `GATEWAY_SATURADA` | La Gateway está ocupada. Intente más tarde. | `… PoolTimeout …` | `test_gateway_errores_proxy.py` |
| G4 | **Respuesta inválida**: el servicio contesta algo que no es HTTP, HTTP mal formado, o un body comprimido roto *(nuevo)* | 502 | `RESPUESTA_INVALIDA` | El servicio respondió de forma inválida. Intente más tarde. | `… RemoteProtocolError …` | `…::test_respuesta_que_no_es_http_responde_502_respuesta_invalida` |
| G5 | **Respuesta inválida**: `2xx` con `Content-Type: application/json` y body que no es JSON *(nuevo)* | 502 | `RESPUESTA_INVALIDA` | (igual a G4) | `Microservicio ms2_taller respondió 200 con JSON inválido (request_id=…)` — sin el body | `…::test_200_con_json_roto_responde_502_respuesta_invalida` |
| G6 | `4xx/5xx` del servicio **sin** JSON (texto, HTML, traza) | mismo | `ERROR_MICROSERVICIO` (`RUTA_NO_ENCONTRADA` / `METODO_NO_PERMITIDO` para 404/405) | El servicio respondió con un error inesperado. | `Microservicio respondió 500 sin cuerpo JSON (request_id=…)` | `…::test_500_en_texto_no_filtra_la_traza_interna` |
| G7 | `4xx/5xx` del servicio **con** JSON | mismo | — (pasa tal cual) | el `detail` del servicio | — (lo registra el servicio) | `…::test_503_json_del_servicio_pasa_tal_cual_con_su_request_id` |
| G8 | Body sobre el límite del prefijo (1 MiB JSON, 12 MiB `evidencias`) | 413 | `CUERPO_DEMASIADO_GRANDE` | El cuerpo de la petición supera el tamaño permitido | `Body sobre el límite para 'evidencias' …` | `test_gateway_rechazos_evidencias.py` |
| G9 | **Cliente corta la subida** mientras la Gateway lee el body *(nuevo)* | 400 | `SOLICITUD_INTERRUMPIDA` | La solicitud se interrumpió antes de recibirse completa. | `Solicitud interrumpida por el cliente en '/evidencias' (request_id=…)` (INFO) | `…::test_subida_interrumpida_no_llega_al_microservicio` |
| G10 | Prefijo sin microservicio | 404 | `RUTA_NO_ENCONTRADA` | No hay microservicio para '/x' | — | `test_gateway_rutas.py` |
| G11 | Excepción no prevista en la Gateway | 500 | `ERROR_INTERNO` | Ocurrió un error inesperado en la Gateway. | traza completa (solo en el log) | `test_gateway_formato.py` |

Antes de la Semana 10, G4 se informaba como "servicio no disponible" (aunque el
servicio sí estaba arriba), G5 llegaba al cliente como un `200` que la web no
podía leer, y G9 terminaba como `500` con traza en el log.

Timeouts vigentes (`gateway/config.py`): conectar 3 s; leer/escribir 15 s
(60 s para `evidencias`); pool 5 s; por servicio con
`GATEWAY_MS<n>_TIMEOUT_SECONDS`.

## 3. Servicio multimedia (MS4) y transferencias

Tramos de una subida: `cliente ──(1)──► Gateway ──► MS4 ──(2)──► MinIO/S3`.

| # | Escenario | Estado | Mensaje | ¿Quedan residuos? | Log de MS4 | Prueba |
|---|---|---|---|---|---|---|
| M1 | Multipart truncado (falta la frontera de cierre) | 4xx | validación de FastAPI | No | `evento=solicitud … estado_http=4xx` | `test_ms4_fallos_transferencia.py::test_multipart_truncado_se_rechaza_sin_subir_nada` |
| M2 | El cliente se desconecta a mitad de la subida (directo a MS4) | — (cliente ya no está) | — | No | — | `…::test_desconexion_del_cliente_a_mitad_de_la_subida_no_deja_residuos` |
| M3 | MinIO inalcanzable al subir | 503 | El almacenamiento de evidencias no está disponible | No | `evento=subida_fallida motivo=almacenamiento_no_disponible servicio=s3 error=EndpointConnectionError` | `…::test_minio_inalcanzable_responde_503_sin_residuos` |
| M4 | **MinIO guardó el archivo pero la confirmación se perdió** (timeout de lectura) *(nuevo)* | 503 | (igual a M3) | **No**: MS4 borra la clave antes de responder | `evento=subida_fallida … error=ReadTimeoutError` | `…::test_respuesta_perdida_de_minio_no_deja_archivo_huerfano` |
| M5 | Igual a M4 y además el borrado falla *(nuevo)* | 503 | (igual a M3) | 1 objeto sin fila, **marcado** | `evento=compensacion_fallida motivo=subida_interrumpida pendiente_limpieza=True` (sin la clave) | `…::test_si_el_borrado_tambien_falla_queda_marcado_y_la_conciliacion_lo_encuentra` |
| M6 | La base falla al guardar después de subir | 503 | No se pudo guardar la evidencia, intenta nuevamente | No (compensación de la Semana 6) | `evento=subida_fallida motivo=base_no_disponible` | `test_ms4_errores_carga.py` |
| M7 | Archivo ilegible / vacío / dañado / formato no permitido / muy grande | 400 / 422 / 415 / 413 | mensaje específico | No (se valida antes de subir) | `evento=subida_rechazada motivo=…` | `test_ms4_validacion_contenido.py`, `test_ms4_limites_archivos.py` |
| M8 | MS2 o MS3 no responden al validar la orden/presupuesto | 503 | El servicio de órdenes/presupuestos no está disponible | No | `evento=subida_fallida …` | `test_ms4_asociacion_ordenes.py` |
| M9 | M4 visto a través de la Gateway | 503 | (igual a M3), tal cual | No | Gateway: nada; MS4: M4 | `…::test_respuesta_perdida_llega_por_la_gateway_como_503_de_ms4` |

Limpieza de lo que quede marcado (M5): `python scripts/limpiar_huerfanos_ms4.py`
(simulación) y con `--eliminar` para borrar. Solo toca objetos con la
convención de clave de MS4 y más antiguos que 60 minutos.

## 4. Correlación (`X-Request-ID`)

- La Gateway asigna el ID (o respeta el del cliente si cumple
  `^[A-Za-z0-9-]{1,128}$`) y lo reenvía al microservicio.
- MS1, MS2 y MS3 (`shared/correlacion.py`) y MS4 (`services/registro.py`) lo
  leen, lo devuelven en toda respuesta y lo reenvían en sus llamadas a otros
  servicios (MS3→MS2, MS2→MS1, MS2→MS3, MS4→MS2, MS4→MS3).
- Cada servicio escribe una línea por petición:
  `evento=solicitud servicio=ms2_taller request_id=<id> metodo=GET ruta=/ordenes/7 estado_http=503 duracion_ms=3012`.
- Diagnóstico: copiar la "Referencia" del mensaje de error de la web y buscar
  `request_id=<id>` en los logs de la Gateway y de cada servicio.

Detalle y decisiones: `estudio-correlacion-logs.md` (sección Semana 10).
Pruebas: `tests/test_correlacion_servicios.py`.

## 5. Cómo reproducir a mano (entorno local con Docker)

Levantar todo con `docker compose up` (ver `ambiente-pruebas.md`) y la web en
`http://localhost:5173`.

| Escenario | Cómo provocarlo | Qué mirar |
|---|---|---|
| G1 servicio caído | Detener MS2 (`docker compose stop` del servicio MS2, o cerrar su `uvicorn`) y abrir **Vehículos** en la web | Mensaje "El servicio no está disponible…" con "Referencia: …"; en la consola de la Gateway, `Fallo de red … ConnectError` con el mismo ID |
| G2 timeout | `python scripts/simular_fallos_gateway.py --modo lento --puerto 8102` y la Gateway con `GATEWAY_MS2_URL=http://127.0.0.1:8102`; abrir **Vehículos** | `504` "El servicio tardó demasiado…" tras 15 s (o el valor de `GATEWAY_MS2_TIMEOUT_SECONDS`) |
| G4 / G5 respuesta inválida | Igual que G2 con `--modo no-http` o `--modo json-roto` | `502` "El servicio respondió de forma inválida…" |
| G6 error sin JSON | Igual que G2 con `--modo 500-texto` | `500` "El servicio respondió con un error inesperado." sin la traza |
| M3 MinIO caído | Detener el contenedor de MinIO e intentar **Subir evidencia** en una orden | "El almacenamiento de evidencias no está disponible" + Referencia; ningún archivo ni fila nuevos |
| Correlación | `curl -i -H "X-Request-ID: demo-123" http://localhost:8000/api/health` y cualquier ruta de negocio | Cabecera `X-Request-ID: demo-123` en la respuesta y `request_id=demo-123` en los logs |

## 6. Dónde se ve en la web

- Paneles de error (`ErrorState`), banner sin conexión (`OfflineBanner`) y el
  formulario de subida de evidencias muestran el `detail` y la línea
  **"Referencia: <request_id>"**.
- Subida de evidencias: `/admin/ordenes/:id/evidencias` (Administrador) y la
  sección de evidencias de la orden del Mecánico.
