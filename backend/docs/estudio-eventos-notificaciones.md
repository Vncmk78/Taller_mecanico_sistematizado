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

## Recomendación

Mantener la autoridad sobre cada cambio en el microservicio que posee el
dominio. Cuando una operación de MS2 confirma una transición que debe avisarse,
MS2 debe registrar en su propia transacción el cambio de estado, el historial y
un registro de salida (outbox) mínimo. Un proceso de MS2 envía luego ese evento
por HTTP al contrato de recepción que publique MS1 y reintenta si MS1 no está
disponible. No hace falta introducir un broker para el alcance actual.

MS1 valida el contrato, determina destinatarios según identidad y permisos,
crea el aviso lógico de forma idempotente y gestiona por separado los canales y
sus resultados de entrega. La clave estable del evento permite repetir el
envío desde MS2 sin duplicar el aviso. Un error al entregar correo o push se
registra en MS1 y no deshace la operación de negocio.

El outbox es una recomendación para no perder el aviso si el proceso cae entre
guardar el cambio y llamar a MS1. La sistematización requiere solicitudes por
API y tolerancia a fallos de canales, pero no prescribe outbox ni transporte;
por eso el patrón debe confirmarse antes de implementarlo.

## Borrador conceptual del evento

El contrato entre microservicios debería transmitir solo los datos necesarios
para identificar el hecho, resolver la notificación y correlacionarla. Como
borrador sujeto a aprobación:

```json
{
  "evento_id": "uuid estable generado por MS2",
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

## Decisiones pendientes antes de implementar

1. Confirmar el outbox reintentable como estrategia de publicación.
2. Acordar ruta interna, autenticación servicio-a-servicio y errores del contrato
   MS2 → MS1; hoy no existe un contrato de notificaciones.
3. Aprobar nombres/versionado de eventos y la lista de hechos que generan aviso.
   La sistematización enumera decisiones de presupuesto, cambios de estado,
   disponibilidad para retiro, cancelaciones, solicitudes de nueva atención,
   respuestas administrativas y alertas de stock.
4. Definir idempotencia y retención de eventos/avisos, intervalos y límite de
   reintentos, y tratamiento de mensajes atascados.
5. Acordar con Integración IV el registro de dispositivos y los datos necesarios
   para push, así como el formato consumido por web/móvil.

Este estudio no implementa ni reserva nombres de endpoints, tablas, eventos,
canales o credenciales; las decisiones anteriores deben reflejarse en los
contratos compartidos antes de ejecutar SCRUM-559 y SCRUM-562.
