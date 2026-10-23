# Estudio: correlación de logs y diagnóstico de flujos distribuidos

## Hallazgos actuales

- La Gateway recibe `X-Request-ID`; si falta o no cumple `^[A-Za-z0-9-]{1,128}$`,
  genera un UUID. Lo guarda en `request.state.request_id` y lo devuelve en la
  respuesta.
- El proxy reenvía el mismo identificador al microservicio destino. La API
  documenta la cabecera y la incorpora al error común como `error.request_id`.
- Los errores de red y errores internos de la Gateway se registran con
  `request_id`; el cliente recibe un mensaje genérico y la cabecera de
  correlación.
- MS4 conserva el identificador en los metadatos de las evidencias.
- MS1, MS2 y MS3 no tienen hoy middleware o logging de negocio que adjunte el
  `X-Request-ID` entrante a sus logs. La búsqueda en el código encuentra el
  logging centralizado en Gateway; los servicios registran el dato en MS4, pero
  no correlacionan sus consultas/cambios de estado en logs.
- En flujos síncronos MS3↔MS2, el JWT y las referencias de orden/decisión
  permiten entender parte del flujo, pero no sustituyen una clave común de
  solicitud. Cuando un POST devuelve timeout, el resultado puede estar
  confirmado; el ID de decisión/envío permite el reintento idempotente.

## Diagnóstico práctico con la implementación actual

1. Copiar `X-Request-ID` de la respuesta HTTP o `error.request_id`.
2. Buscar ese ID en los logs de Gateway para ubicar la ruta, el prefijo y el
   error de transporte, si ocurrió allí.
3. Usar el mismo valor como filtro al consultar metadatos de evidencia MS4.
4. En MS1–MS3, usar la hora, endpoint e IDs de dominio (orden, presupuesto,
   decisión) para correlacionar manualmente; los logs de esos servicios aún no
   comparten automáticamente el request ID.

Los registros de estado, decisión, auditoría o envío son evidencia de negocio
persistida. Los logs describen la ejecución técnica; ninguno reemplaza al otro.

## Recomendación para una tarea de implementación posterior

Agregar en cada microservicio un middleware ligero que lea `X-Request-ID` y lo
exponga al contexto de logging de esa petición. Los logs estructurados deberían
incluir, como mínimo, `service`, `request_id`, ruta, método, status y duración;
las llamadas HTTP salientes deben propagar el mismo ID. Para peticiones sin ID,
el servicio debe generarlo y devolverlo. Mantener los mensajes sin contraseñas,
JWT, body completo ni datos personales innecesarios.

Una instrumentación distribuida mayor (por ejemplo OpenTelemetry o un backend
centralizado de trazas) requiere una decisión de infraestructura aparte y no es
necesaria para aprovechar el identificador que ya entrega la Gateway.

## Fuentes revisadas

- `gateway/middleware.py`, `gateway/routers/proxy.py` y `gateway/errores.py`.
- `backend/docs/contratos-api-gateway.md`, sección “Cabecera X-Request-ID”.
- `backend/docs/maquina-estados-ordenes.md`, sección de trazabilidad, auditoría
  y eventos de dominio.
- Modelos y entrada HTTP de `services/ms4_evidencias`.
