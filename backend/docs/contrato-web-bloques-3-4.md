# Acuerdo de coordinación web/backend: bloques 3 y 4

Fecha: 8 de noviembre de 2026. Base funcional: commit `66f694d`.

Este archivo fija la interfaz para trabajar en paralelo. Es un acuerdo de
implementación: la Entrega A tiene backend y web integrados localmente en
MartinH, pendientes de publicación. La Entrega B también está integrada localmente
con la web de Claude. La Entrega C todavía no está implementada.
Ninguna operación se considera publicada por aparecer aquí. Codex mantiene el backend y OpenAPI;
Claude implementa el frontend por entregas. La integración final debe probarse
contra servicios reales. El contrato 3.0.0 está pendiente de publicación y
puede incluir estas operaciones antes de su primera publicación.

## Organización

- Codex: `backend/`, reglas, transacciones, migraciones, Gateway/OpenAPI,
  notificaciones del backend y pruebas de integración.
- Claude: únicamente `frontend/` en su copia aislada; entidades, puertos,
  adaptadores, componentes, pantallas y pruebas web.
- Codex integra los commits de Claude en `MartinH`. Cada agente mantiene su
  propio índice Git y directorio de trabajo. No se escribe en la copia del otro.
- Los cambios a este acuerdo los coordina Codex y se comunican a Claude antes
  de que este consuma una interfaz distinta. Claude señala contradicciones;
  no modifica el backend para acomodar la web.

La sistematización de referencia está en
`/Users/martin/Desktop/Integra II/Sistematizacion.docx`, secciones 4.7-4.9.
Las reglas complementarias fueron aprobadas en la conversación. No se agregan
estados a las órdenes ni se implementa reserva de horas.

## Convenciones comunes

- Las rutas siguientes incluyen `/api`. El `apiClient` del frontend ya tiene
  esa base: los servicios web usan `/ordenes/...`, sin duplicar `/api`.
- Todas requieren JWT; identidad y roles salen del token. Fechas y responsable
  los decide el backend. Ningún body acepta esos valores.
- Error de MS2: `{"detail": "mensaje"}`; el 422 también puede tener una lista
  de errores de validación. Los errores de Gateway conservan su formato actual.
- Estados oficiales: 1-6 activos, 7 Entregado, 8 Cancelado. La fecha de
  devolución no modifica el estado 8. Los roles se acumulan.
- Las escrituras no se reintentan automáticamente. Un timeout no demuestra
  que la operación no se guardó: se comprueba con GET y se informa el estado.
- No hay cuentas, órdenes ni respuestas simuladas en producción. Las
  simulaciones se limitan a pruebas automatizadas.

## Entrega A: salida y devolución

Integración local verificada el 8 de noviembre: frontend de Claude incorporado
desde `5244ec2` como `18f58e5`, sobre el backend `a43deb1`. Las 906 pruebas web,
lint y build pasan (dos avisos de lint previos y aviso de tamaño de chunk).
Además, un navegador Chromium contra Gateway, los cuatro servicios y PostgreSQL
descartables comprobó 18 casos, sin simular respuestas de negocio: devolución,
confirmación cancelada, recarga, reintento por otro administrador, GET con ambos
campos, 409 por ingreso compartido, cuenta multirrol y rechazo del Cliente.
Para probar la respuesta perdida se descartó únicamente la respuesta de una
petición real ya procesada; el GET recuperó la auditoría y no hubo otro POST.
Las bases y procesos de esa ejecución se retiraron; la demostración no se migró.
El catálogo `gateway/contratos/consumo_web.py` y su recorrido de pruebas incluyen
la devolución. No implica publicación ni validación de las entregas B y C.

### Operación existente de entrega

`POST /api/ordenes/{orden_id}/entrega`, Administrador. Conserva su body y su
respuesta existentes (incluye los dos campos aditivos de consulta descritos abajo).
El backend agrega el cierre atómico del ingreso físico y conserva la fecha
original ante reintentos. La web no cierra un ingreso por
su cuenta ni deduce la salida de una cancelación.

Las entregas históricas con auditoría válida conservan su respuesta original.
Si les falta la salida del ingreso, no se completa con una fecha inferida:
la revisión histórica queda separada de esta entrega.

### Devolver el vehículo de una orden cancelada

`POST /api/ordenes/{orden_id}/devolucion`, Administrador; body obligatorio `{}`.

Primera ejecución y repetición válida: **200**. Devuelve todos los campos de
`OrdenRespuesta` más `devuelto_en` (fecha ISO 8601 con zona, no nula) y
`devuelto_por_id` (entero positivo, no nulo). Ejemplo de fixture:

```json
{
  "orden_id": 25,
  "vehiculo_id": 9,
  "ingreso_id": 12,
  "estado_codigo": 8,
  "mecanico_actual_id": null,
  "creado_por_id": 3,
  "creado_en": "2026-11-08T12:00:00Z",
  "actualizado_en": "2026-11-08T13:00:00Z",
  "devuelto_en": "2026-11-08T13:00:00Z",
  "devuelto_por_id": 3
}
```

No incluye `historial_id`: no es una transición de estado. La auditoría se
conserva en los campos de devolución. El ingreso se cierra en la misma
transacción. Repetir devuelve la fecha y responsable originales.

Errores: 401 sin sesión válida; 403 sin rol Administrador; 404 orden
inexistente; 409 estado/ingreso incompatible, incluida otra orden activa que
comparte el ingreso; 422 body o identificador inválido; 500 rollback por fallo
de persistencia. La web muestra el `detail` del impedimento y no fuerza el cierre.

### Consulta para restaurar la pantalla

Los GET existentes de listado, detalle e historial de órdenes incorporarán
dos campos aditivos: `devuelto_en: string | null` y
`devuelto_por_id: number | null`. Siempre vienen ambos, nulos o con datos.
Las órdenes sin devolución tienen ambos nulos. Después de recargar o perder
una respuesta, consultar el detalle permite comprobar si ya fue registrada.

Frontend A:

1. Ofrecer la acción solo al Administrador en una orden Cancelada sin
   devolución registrada; una cuenta multirrol con Administrador también puede.
2. Pedir confirmación explícita antes del POST y bloquear el doble envío.
3. Mostrar responsable y fecha devueltos por el servidor; mantener Cancelado.
4. Si ya hay devolución, mostrar los datos y no ofrecer otra devolución.
5. Mostrar 409 sin éxito falso; gestionar carga, error y resultado incierto.
6. Reconsultar orden, historial/vehículo y listados afectados conforme a los
   patrones existentes. No cambiar cupos, estados ni fechas desde la web.

## Entrega B: solicitud del Cliente

Backend local implementado en MS2 y web integrada desde `ab8c0dc` como `9365559`:
alta idempotente, listado y detalle con el contrato siguiente. Migración
`0014_nueva_atencion_ms2`, posterior a
`0013_orden_activa_ms2`: crea solo `solicitud_nueva_atencion`, sus restricciones
e índices, sin modificar filas existentes. No se ejecuta en ambientes compartidos
ni en la demostración sin diagnóstico previo. El esquema incluye los campos de
revisión y vínculo necesarios para consultar la entidad completa, pero B no
expone operaciones para revisarla o generar órdenes: esas siguen en C.

El alta bloquea vehículo, orden cancelada y luego solicitud vigente, en ese
orden, compatible con entrega/devolución y creación de órdenes. La revisión y
la generación de C deberán respetar ese orden si necesitan esos mismos bloqueos.
El índice A protege también frente a escrituras que omitan el servicio.
No exige devolución previa, no crea ingreso/orden/historial/outbox, ni consulta
otros microservicios para registrar una solicitud. El aviso de revisión sigue
pendiente de C. El contrato 3.0.0 continúa sin publicar.

Integración comprobada: 957 pruebas web, lint/build y 101 pruebas de contrato/API
aprobadas; 31 comprobaciones en Chromium contra Gateway, los cuatro servicios y
PostgreSQL descartables, incluidos 201/200/409, respuesta perdida, paginación,
filtros, multirrol y vista móvil. Los casos de revisión y vínculo usan datos
precargados de prueba: no acreditan que C esté implementada. Las bases y procesos
se retiraron, sin migrar la demostración.

El detalle del portal Cliente consulta `solo_propietario=true` y solo ofrece la
sección tras confirmación de propiedad. Una copia administrativa en caché no la
acredita. Esto también se aplica a Cliente+Administrador o Cliente+Mecánico;
para consultar órdenes ajenas como Administrador, los enlaces usan su portal.
El catálogo de consumo web incluye las tres operaciones de B.

La entidad `SolicitudNuevaAtencion` tiene estos campos JSON:

```typescript
type Situacion = 'pendiente' | 'aceptada' | 'rechazada';
interface SolicitudNuevaAtencion {
  solicitud_id: number;
  orden_cancelada_id: number;
  vehiculo_id: number;
  cliente_usuario_id: number;
  descripcion: string;
  solicitada_en: string;
  situacion: Situacion;
  respuesta: string | null;
  revisor_id: number | null;
  revisada_en: string | null;
  orden_generada_id: number | null;
}
```

Todas las propiedades se publican y se serializan, incluidas las nulas.

- `POST /api/ordenes/{orden_id}/nueva-atencion`: Cliente propietario; body
  `{"descripcion": "..."}`. Texto sin espacios exteriores, no vacío,
  máximo 2000 caracteres. 201 devuelve la solicitud nueva; 200 devuelve una
  pendiente existente con idéntica descripción. 403 sin Cliente; 404 inexistente
  o ajena; 409 antecedente no Cancelado u otra solicitud pendiente/aceptada;
  422 datos inválidos. No crea una orden ni consume cupo.
- `GET /api/ordenes/nuevas-atenciones`: Cliente ve las propias; Administrador
  ve todas; Mecánico sin esos roles recibe 403. Filtros opcionales `situacion`,
  `orden_cancelada_id`, `orden_generada_id`; `limit` por defecto 20, de 1 a 100;
  `offset` por defecto 0, no negativo. Respuesta 200
  `{items: SolicitudNuevaAtencion[], total: number, limit: number, offset: number}`.
  Orden descendente por fecha e ID. Una cuenta Cliente+Administrador tiene
  acceso administrativo; no se restringe artificialmente al rol Cliente.
- `GET /api/ordenes/nuevas-atenciones/{solicitud_id}`: 200 con la entidad;
  Cliente propietario o Administrador; 403 sin esos roles; 404 inexistente o
  ajena. Las listas vacías no son errores.

Después de un rechazo se permite otra solicitud conservando la anterior.
Una pendiente o aceptada bloquea otra sobre el mismo antecedente, incluso
si la aceptada ya generó orden (índice A). Si esa nueva orden se cancela, se
solicita sobre ella. No se agrega una situación «completada» por generar orden.

## Entrega C: revisión y generación administrativa

- `POST /api/ordenes/nuevas-atenciones/{solicitud_id}/revision`: Administrador.
  Body `{"decision": "aceptada" | "rechazada", "respuesta": "..."}`; texto
  recortado y no vacío, sin un máximo inventado por el frontend. 200 devuelve
  la solicitud revisada; repetir la misma decisión y respuesta devuelve la
  existente. Una revisión confirmada no se edita: 409 si cambia su contenido.
  403 sin Administrador; 404 inexistente; 422 datos inválidos.
- `POST /api/ordenes/nuevas-atenciones/{solicitud_id}/orden`: Administrador,
  body obligatorio `{}`. 201 con `{solicitud: SolicitudNuevaAtencion,
  orden: OrdenRespuesta}`; 200 con la misma asociación si ya se había generado.
  La nueva orden comienza Recibido, sin mecánico, y conserva los antecedentes.
  409 solicitud no aceptada, antecedente incompatible, vehículo con orden
  activa o rechazo de cupo; 403, 404, 422 y 500 según el caso.

Se permite autorrevisión de una cuenta Cliente+Administrador, conservando
responsable y fecha. La creación y el vínculo se guardan en una sola
transacción. Ante respuesta perdida, el GET de la solicitud permite comprobar
`orden_generada_id` sin atribuir otras órdenes del historial a esa petición.

Los avisos de revisión requieren implementación de backend. Claude mantiene
la bandeja actual y no inventa eventos o respuestas de MS1; Codex comunicará
cualquier extensión de ese contrato antes de pedir cambios a la web.

## Cierre y comunicación

Cada entrega de Claude termina en pruebas, revisión y commit local. Informar
hash, archivos, verificaciones ejecutadas y lo pendiente de validar contra el
backend real. No presentar una prueba con simulaciones como integración real.
Sin push, merge, rebase, reset ni cambio de rama por cuenta de Claude.
