# Estudio: eventos y notificaciones desacopladas del dominio

## Propósito

Definir una dirección técnica para comunicar cambios relevantes del dominio de
órdenes a las notificaciones transversales sin trasladar reglas de MS2 a MS1 ni
crear dependencias entre sus bases de datos.

## Hallazgos y restricciones

- La sistematización final §1.2 y §4.5 asigna el módulo, el almacenamiento de
  avisos y los resultados de entrega por canal a MS1. Los demás dominios piden
  avisos mediante contratos de API.
- Los avisos se dirigen al cliente afectado o al personal autorizado. Se
  conservan intentos por canal, se permite reintentar fallos sin duplicar el
  aviso lógico y un fallo de correo o push no revierte el cambio de negocio.
- MS1 debe ofrecer consulta web/móvil, correo y push. La integración del
  registro/recepción móvil corresponde a Integración IV.
- La arquitectura define cuatro microservicios y bases independientes. No se
  deben crear claves foráneas entre MS2 y MS1 ni compartir sus tablas.
- Hoy MS1 solo publica autenticación y usuarios; aún no tiene modelos, rutas,
  migraciones ni contratos de notificaciones.
- `EventoOrden` en MS2 es una clave interna para validar transiciones. No es un
  evento publicado ni persistido independientemente. No hay bus, broker, outbox
  ni consumidores; la comunicación actual entre servicios usa HTTP síncrono.

## Decisión de implementación

Mantener la autoridad sobre cada cambio en el microservicio que posee el
dominio. Cuando una operación de MS2 confirma una transición que debe avisarse,
MS2 debe registrar en su propia transacción el cambio de estado, el historial y
un registro de salida (outbox) mínimo. Un proceso de MS2 envía luego ese evento
por HTTP al contrato de recepción que publique MS1 y reintenta si MS1 no está
disponible. No hace falta introducir un broker para el alcance actual.

MS1 valida el contrato y que el destinatario sea un Cliente activo, crea el aviso
lógico de forma idempotente y lo expone en su bandeja autenticada. La clave
estable del evento permite repetir el envío desde MS2 sin duplicar el aviso.
Esta implementación persiste y consulta el canal web; no afirma que correo o
push hayan sido enviados. Esos canales requieren proveedores y, para push, el
registro de dispositivos de Integración IV.

Se aprobó el outbox transaccional en MS2 con envío HTTP reintentable a MS1 y un
secreto dedicado entre ambos servicios, configurado por entorno y distinto del
secreto JWT. El worker reintenta con espera exponencial de 1, 2, 4… segundos,
con tope de 300 segundos y sin descartar automáticamente eventos pendientes.
MS1 utiliza `evento_id` como clave única para que un reintento no duplique el
aviso lógico.

## Borrador conceptual del evento

El contrato entre microservicios debería transmitir solo los datos necesarios
para identificar el hecho, resolver la notificación y correlacionarla. Como
borrador sujeto a aprobación:

```json
{
  "evento_id": "UUID estable generado por MS2",
  "tipo": "orden.estado_cambiado",
  "ocurrido_en": "fecha-hora ISO 8601 con zona",
  "orden_id": 123,
  "vehiculo_id": 456,
  "cliente_usuario_id": 7,
  "estado_anterior": "En reparación",
  "estado_nuevo": "Listo",
  "request_id": "id de correlación opcional"
}
```

MS2 obtiene las identidades desde sus referencias lógicas y el actor desde la
sesión autenticada; no acepta del cliente destinatarios arbitrarios. MS1
comprueba el destinatario/rol con su propia fuente de identidad y no confía en
que la aplicación cliente envíe el texto final ni los canales. El payload no
debería incluir credenciales, datos de contacto innecesarios, ni el contenido
completo de la orden.

## Alternativas consideradas

| Alternativa | Ventaja | Costo o riesgo | Evaluación |
| --- | --- | --- | --- |
| Llamada HTTP directa después de guardar la transición | Simple y coherente con la comunicación existente | Si MS1 falla o MS2 cae antes de llamar, puede perderse el aviso | Adecuada solo si se acepta reconciliación/reintento operativo |
| Outbox transaccional en MS2 + envío HTTP reintentable a MS1 | El cambio y la intención de avisar quedan persistidos juntos; no exige broker | Requiere tabla, worker, política de reintentos y operación de eventos atascados | Recomendada para entrega confiable sin cambiar la arquitectura |
| Broker/event bus | Aísla productores y consumidores y facilita agregar consumidores | Nueva infraestructura y operación no previstas en el repositorio actual | No recomendada para este alcance sin requerimiento y aprobación explícitos |

## Contrato implementado y límites actuales

El contrato de este incremento es `POST /interno/eventos/ordenes/estado` en MS1,
fuera de la Gateway. Se autentica con `X-Service-Token`; MS1 lee
`MS1_EVENT_SHARED_SECRET` y MS2 envía `MS2_EVENT_SHARED_SECRET`. Ambos valores
deben ser idénticos, aleatorios, de al menos 32 caracteres y estar fuera de Git.
La bandeja está disponible en `GET /api/notificaciones`; solo devuelve avisos
del usuario autenticado.

El payload implementado es el borrador mostrado arriba. MS2 lo encola para los
cambios efectivos de estado que pasan por `registrar_historial_estado`, dentro
de la misma transacción que el historial. MS1 genera un mensaje genérico para el
Cliente afectado; no acepta texto libre ni destinatarios arbitrarios.

Quedan fuera de este incremento la entrega de email/push, los resultados por
canal y los tipos de aviso distintos de cambio de estado (decisión de
presupuesto, disponibilidad, solicitud de nueva atención y alertas de stock).
El envío push requiere coordinación con Integración IV. Los errores de eventos
pendientes quedan visibles en `evento_outbox.ultimo_error` e `intentos` para
diagnóstico; no hay descarte automático ni política de retención configurada.

El contrato puede ampliarse con nuevos tipos cuando las tareas de esos eventos
se implementen. No se crea un broker y no se comparten tablas entre servicios.
