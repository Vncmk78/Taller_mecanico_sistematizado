# Presupuestos: revisión administrativa y recuperación de 503

- Gateway: `http://127.0.0.1:8100` · duración 3.4 s · resultado: **APROBADO**
- Pasos HTTP: 56/56 · comprobaciones: 19/19
- Llamadas bloqueadas por el proxy de fallos: 5

## Pasos HTTP

| Flujo | Paso | Método y ruta | Esperado | Obtenido | ms |
|---|---|---|---|---|---|
| Acceso | ✅ Login cliente@pruebas.cl | `POST /api/auth/login` | 200 | 200 | 320 |
| Acceso | ✅ Login mecanico@pruebas.cl | `POST /api/auth/login` | 200 | 200 | 303 |
| Acceso | ✅ Login administrador@pruebas.cl | `POST /api/auth/login` | 200 | 200 | 310 |
| Acceso | ✅ Login cliente-mecanico@pruebas.cl | `POST /api/auth/login` | 200 | 200 | 318 |
| Acceso | ✅ Login mecanico-administrador@pruebas.cl | `POST /api/auth/login` | 200 | 200 | 302 |
| R1 | ✅ Cliente registra vehículo | `POST /api/vehiculos` | 201 | 201 | 11 |
| R1 | ✅ Administrador crea la orden | `POST /api/ordenes` | 201 | 201 | 18 |
| R1 | ✅ Usuario actual | `GET /api/auth/me` | 200 | 200 | 7 |
| R1 | ✅ Administrador asigna mecánico | `PUT /api/ordenes/{orden_id}/mecanico` | 200 | 200 | 37 |
| R1 | ✅ Mecánico prepara el borrador | `POST /api/presupuestos` | 201 | 201 | 31 |
| R1 | ✅ Mecánico intenta enviar → 403 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 403 | 403 | 3 |
| R1 | ✅ Cliente+Mecánico (sin Administrador) intenta enviar → 403 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 403 | 403 | 3 |
| R1 | ✅ Administrador revisa: corrige el precio | `PUT /api/presupuestos/{presupuesto_id}/versiones/{numero}/items` | 200 | 200 | 49 |
| R1 | ✅ Administrador envía al cliente | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 200 | 200 | 106 |
| R1 | ✅ Consulta la orden | `GET /api/ordenes/{orden_id}` | 200 | 200 | 9 |
| R1 | ✅ Cliente consulta su presupuesto | `GET /api/presupuestos/{presupuesto_id}` | 200 | 200 | 39 |
| R1 | ✅ Mecánico intenta reenviar → 403 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 403 | 403 | 4 |
| R1 | ✅ Cliente registra vehículo | `POST /api/vehiculos` | 201 | 201 | 10 |
| R1 | ✅ Administrador crea la orden | `POST /api/ordenes` | 201 | 201 | 19 |
| R1 | ✅ Usuario actual | `GET /api/auth/me` | 200 | 200 | 8 |
| R1 | ✅ Administrador asigna mecánico | `PUT /api/ordenes/{orden_id}/mecanico` | 200 | 200 | 37 |
| R1 | ✅ Mecánico prepara el borrador | `POST /api/presupuestos` | 201 | 201 | 33 |
| R1 | ✅ Mecánico+Administrador (multirrol) envía → 200 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 200 | 200 | 86 |
| R2 | ✅ Cliente registra vehículo | `POST /api/vehiculos` | 201 | 201 | 10 |
| R2 | ✅ Administrador crea la orden | `POST /api/ordenes` | 201 | 201 | 18 |
| R2 | ✅ Usuario actual | `GET /api/auth/me` | 200 | 200 | 8 |
| R2 | ✅ Administrador asigna mecánico | `PUT /api/ordenes/{orden_id}/mecanico` | 200 | 200 | 39 |
| R2 | ✅ Mecánico prepara el borrador | `POST /api/presupuestos` | 201 | 201 | 35 |
| R2 | ✅ Envío con la verificación de la orden caída → 503 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 503 | 503 | 22 |
| R2 | ✅ Administrador consulta el presupuesto | `GET /api/presupuestos/{presupuesto_id}` | 200 | 200 | 9 |
| R2 | ✅ Envío normal tras restablecer MS2 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 200 | 200 | 139 |
| R3 | ✅ Cliente registra vehículo | `POST /api/vehiculos` | 201 | 201 | 12 |
| R3 | ✅ Administrador crea la orden | `POST /api/ordenes` | 201 | 201 | 29 |
| R3 | ✅ Usuario actual | `GET /api/auth/me` | 200 | 200 | 8 |
| R3 | ✅ Administrador asigna mecánico | `PUT /api/ordenes/{orden_id}/mecanico` | 200 | 200 | 40 |
| R3 | ✅ Mecánico prepara el borrador | `POST /api/presupuestos` | 201 | 201 | 31 |
| R3 | ✅ Envío con la coordinación caída → 503 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 503 | 503 | 72 |
| R3 | ✅ Presupuesto tras el 503 | `GET /api/presupuestos/{presupuesto_id}` | 200 | 200 | 10 |
| R3 | ✅ Consulta la orden | `GET /api/ordenes/{orden_id}` | 200 | 200 | 13 |
| R3 | ✅ Reintento con MS2 aún caído → 503 (sigue guardado) | `POST /api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion` | 503 | 503 | 46 |
| R3 | ✅ Mecánico intenta reintentar la aplicación → 403 | `POST /api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion` | 403 | 403 | 7 |
| R3 | ✅ Administrador recupera el envío | `POST /api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion` | 200 | 200 | 72 |
| R3 | ✅ Consulta la orden | `GET /api/ordenes/{orden_id}` | 200 | 200 | 12 |
| R3 | ✅ Reintento repetido → 200 idempotente | `POST /api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion` | 200 | 200 | 49 |
| R3 | ✅ Volver a enviar la misma versión → 409 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | 409 | 409 | 64 |
| R3 | ✅ Historial de la orden | `GET /api/ordenes/{orden_id}/historial` | 200 | 200 | 22 |
| R4 | ✅ Cliente aprueba con la coordinación caída → 503 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/decision` | 503 | 503 | 80 |
| R4 | ✅ Presupuesto tras el 503 | `GET /api/presupuestos/{presupuesto_id}` | 200 | 200 | 32 |
| R4 | ✅ Consulta la orden | `GET /api/ordenes/{orden_id}` | 200 | 200 | 9 |
| R4 | ✅ Reintento con MS2 aún caído → 503 | `POST /api/presupuestos/decisiones/{decision_id}/aplicacion` | 503 | 503 | 23 |
| R4 | ✅ Administrador intenta aplicar la decisión del cliente → 403 | `POST /api/presupuestos/decisiones/{decision_id}/aplicacion` | 403 | 403 | 3 |
| R4 | ✅ Cliente recupera su decisión | `POST /api/presupuestos/decisiones/{decision_id}/aplicacion` | 200 | 200 | 54 |
| R4 | ✅ Consulta la orden | `GET /api/ordenes/{orden_id}` | 200 | 200 | 8 |
| R4 | ✅ Reintento repetido → 200 idempotente | `POST /api/presupuestos/decisiones/{decision_id}/aplicacion` | 200 | 200 | 29 |
| R4 | ✅ Decidir otra vez la misma versión → 409 | `POST /api/presupuestos/{presupuesto_id}/versiones/{numero}/decision` | 409 | 409 | 37 |
| R4 | ✅ Historial de la orden | `GET /api/ordenes/{orden_id}/historial` | 200 | 200 | 9 |

## Comprobaciones de datos

| Flujo | Comprobación | Resultado | Detalle |
|---|---|---|---|
| R1 | El Administrador pudo ajustar el precio del borrador | ✅ | total 32500.00 |
| R1 | El envío confirma la aplicación en la orden | ✅ |  |
| R1 | El Cliente ve la versión 1 enviada con el precio revisado | ✅ | enviada 32500.00 |
| R2 | El 503 previo al guardado no trae referencia de reintento | ✅ |  |
| R2 | La versión sigue en borrador (nada se guardó) | ✅ |  |
| R2 | Sin envíos registrados en MS3 | ✅ | envíos=0 |
| R3 | El 503 trae presupuesto_id y la ruta de reintento | ✅ | {"detail": "El presupuesto qued\u00f3 enviado; no se pudo confirmar su aplicaci\u00f3n en MS2. Reintente la aplicaci\u00f3n del env\u00edo inicial.", "presupuesto_id": 9, "orden_id": 12, "envio_confir |
| R3 | El envío quedó guardado (versión enviada) | ✅ |  |
| R3 | La aplicación recuperada corresponde al presupuesto y la orden | ✅ |  |
| R3 | Una sola transición a 'Esperando aprobación' en el historial (API) | ✅ | 1 |
| R3 | Una sola transición 2→3 en historial_estado (MS2) | ✅ | bd=1 |
| R3 | Un solo envío registrado en MS3 | ✅ | bd=1 |
| R4 | El 503 trae decision_id y la ruta de reintento | ✅ | {"detail": "La decisi\u00f3n qued\u00f3 registrada; no se pudo confirmar su aplicaci\u00f3n en MS2. Reintente la misma decisi\u00f3n, sin volver a aprobar ni rechazar.", "decision_id": 5, "orden_id":  |
| R4 | La decisión quedó guardada (versión aprobada) | ✅ |  |
| R4 | La aplicación recuperada corresponde a la decisión | ✅ |  |
| R4 | La orden salió de 'Esperando aprobación' | ✅ | estado 5 |
| R4 | Una sola transición desde 'Esperando aprobación' (API) | ✅ | 1 |
| R4 | Una sola transición al estado final en historial_estado (MS2) | ✅ | bd=1 |
| R4 | Una sola decisión registrada en MS3 | ✅ | bd=1 |

## Hallazgos (no bloquean el recorrido)

- El contrato 3.0.0 no publica el 503 de envío previo al guardado (`{detail}` sin `presupuesto_id`): contrato: (raíz): {'detail': 'No fue posible validar la orden con el servicio de órdenes'} is not valid under any of the given schemas

## Llamadas de MS3 a MS2 bloqueadas (fallo controlado)

- `GET /ordenes/11`
- `POST /ordenes/12/envios-presupuesto`
- `POST /ordenes/12/envios-presupuesto`
- `POST /ordenes/12/decisiones-presupuesto`
- `POST /ordenes/12/decisiones-presupuesto`
