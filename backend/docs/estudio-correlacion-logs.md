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
- MS1, MS2 y MS3 no tienen middleware general que adjunte el `X-Request-ID`
  entrante a todos sus logs. MS2 registra ahora ese identificador cuando falla
  la persistencia de `GET /ordenes`, según el diagnóstico acotado más abajo.
  Esto no añade correlación a los demás endpoints ni a las llamadas salientes.
- En flujos síncronos MS3↔MS2, el JWT y las referencias de orden/decisión
  permiten entender parte del flujo, pero no sustituyen una clave común de
  solicitud. Cuando un POST devuelve timeout, el resultado puede estar
  confirmado; el ID de decisión/envío permite el reintento idempotente.

## Diagnóstico práctico con la implementación actual

1. Copiar `X-Request-ID` de la respuesta HTTP o `error.request_id`.
2. Buscar ese ID en los logs de Gateway para ubicar la ruta, el prefijo y el
   error de transporte, si ocurrió allí.
3. Usar el mismo valor como filtro al consultar metadatos de evidencia MS4.
4. Si falla el listado de órdenes, buscar en MS2 el evento
   `ms2_consulta_ordenes_fallida` con el mismo `request_id`.
5. En el resto de operaciones de MS1–MS3, usar la hora, endpoint e IDs de dominio
   (orden, presupuesto, decisión) para correlacionar manualmente.

Los registros de estado, decisión, auditoría o envío son evidencia de negocio
persistida. Los logs describen la ejecución técnica; ninguno reemplaza al otro.

## Diagnóstico acotado del error 500 de órdenes

El router de MS2 conserva la respuesta pública existente:
`500 {"detail": "No fue posible consultar las órdenes"}`. Después de que el
servicio hace rollback, registra una línea como esta en el log del servidor:

```text
ms2_consulta_ordenes_fallida request_id=integra4-500 tipo=ProgrammingError sqlstate=42703
```

Solo se registra el nombre del tipo de excepción y el SQLSTATE de cinco
caracteres del driver PostgreSQL. No se incluye la excepción completa, traza,
SQL, parámetros, JWT, conexión ni identidad del usuario. Un request ID ausente
o distinto del formato de la Gateway se sustituye por `no-disponible`; también
se usa ese valor cuando el driver no proporciona un SQLSTATE válido.

Según el [catálogo de PostgreSQL](https://www.postgresql.org/docs/current/errcodes-appendix.html),
`42703` indica una columna inexistente y `42P01` una tabla inexistente. Esos
códigos permiten orientar la revisión del esquema sin exponer el SQL. No
identifican por sí solos qué migración falta: hay que contrastar la versión y
columnas de la base con el commit realmente desplegado.

La regresión en `tests/test_ordenes_api.py` reproduce una columna de historial
ausente en SQLite en memoria: los tres roles pasan de `200` a `500` y recuperan
`200` al restaurarla. Es evidencia de que esa diferencia de esquema puede causar
el síntoma, no una confirmación de la causa de producción ni una prueba sobre
PostgreSQL. El SQLSTATE PostgreSQL se verifica con errores simulados del driver.

Esta instrumentación solo estará disponible en producción después de integrar
y desplegar el cambio; no aplica migraciones ni corrige automáticamente la base.

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
