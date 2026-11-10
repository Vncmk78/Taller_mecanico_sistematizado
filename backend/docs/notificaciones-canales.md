# Notificaciones por web, correo y push

MS1 conserva la bandeja, los dispositivos y los resultados de cada canal en su
propia base. MS2 y MS3 conservan hechos en sus propias outbox dentro de la
transacción de negocio y los publican por HTTP con credenciales de servicio.
No hay claves foráneas ni consultas SQL entre bases de microservicios.

## Eventos y destinatarios

| Hecho | Destinatario | Canales |
|---|---|---|
| Cambio de estado, incluido Listo y Cancelado | Cliente propietario | Bandeja, correo y dispositivos push activos |
| Solicitud de nueva atención | Administradores activos | Bandeja, correo y push |
| Respuesta administrativa a la solicitud | Cliente solicitante | Bandeja, correo y push |
| Presupuesto enviado | Cliente propietario, resuelto por API de MS2 | Bandeja, correo y push |
| Presupuesto aprobado o rechazado | Administradores activos | Bandeja, correo y push |
| Stock cruza a menor que el umbral efectivo | Administradores activos | Bandeja y correo |

Una cancelación no acredita la salida física. El aviso Listo invita a coordinar
el retiro; no registra la entrega del vehículo. El aviso de decisión confirma
el hecho de MS3, no asegura que MS2 ya haya aplicado su efecto.

El umbral general se configura antes de activar alertas (§4.6, decisión
confirmada por el usuario). Mientras no exista, ni los umbrales particulares
activan avisos o el listado de stock bajo. Un general de **0 sí está configurado**.
Después, el particular prevalece y un particular vacío usa el general.
Stock igual al umbral no activa alerta. Se evalúan cambios de stock, cambios de
umbral y altas de repuestos; no se vuelve a avisar mientras persiste la condición.
Si el stock se recupera y vuelve a cruzar, se crea un evento nuevo.

## Contratos internos

- MS2 → MS1: contratos de cambios de estado y solicitudes/revisiones existentes,
  autenticados con `MS2_EVENT_SHARED_SECRET` / `MS1_EVENT_SHARED_SECRET`.
- MS3 → MS1: `POST /interno/eventos/ms3/aviso`, hechos discriminados
  `presupuesto.enviado`, `presupuesto.decidido`, `stock.alerta`.
  `MS3_EVENT_SHARED_SECRET` / `MS1_MS3_EVENT_SHARED_SECRET` deben coincidir.
- MS1 → MS2: `GET /interno/notificaciones/ordenes/{id}/destinatario` devuelve
  solamente `orden_id`, `vehiculo_id`, `cliente_usuario_id`.
  `MS1_MS2_NOTIFICATION_SECRET` / `MS2_NOTIFICATION_LOOKUP_SECRET` deben coincidir.

Los secretos de cada par son distintos del JWT y de los demás pares. Se envían
en `X-Service-Token`. Sin configuración, las rutas internas responden 503;
credencial inválida, 401. Los cuerpos rechazan campos extra y no permiten que el
productor elija un correo o destinatario arbitrario. No están en el contrato
público de la Gateway.

El envío y la decisión se encolan junto con su persistencia en MS3. Un error al
conservar el evento revierte la operación completa. Una caída de MS1 deja el
hecho pendiente y **no revierte** la operación ya confirmada. La misma UUID se
reintenta; la bandeja deduplica por evento y, para el personal, por destinatario.
El receptor responde solo después de confirmar avisos y canales en MS1.

## API pública para web e Integración IV

Todas las rutas usan JWT mediante `/api` en la Gateway:

| Operación | Comportamiento |
|---|---|
| `POST /api/notificaciones/dispositivos` | `{token, plataforma}`; plataformas android/ios/web. 201 nuevo, 200 registrado. Token privado; la respuesta nunca lo devuelve. Un alta concurrente puede responder 409 y debe consultarse/reintentarse. |
| `GET /api/notificaciones/dispositivos` | Metadatos de dispositivos propios, incluidos los desactivados. |
| `DELETE /api/notificaciones/dispositivos/{uuid}` | Desactiva el propio; 204 idempotente, 404 ajeno/inexistente. |
| `GET /api/notificaciones/{id}/entregas` | Canales, estados e historial de intentos propios; 404 ajeno. |
| `POST /api/notificaciones/{id}/reintentos` | Encola los canales fallidos/sin configuración y permite agregar los dispositivos actualmente registrados. No vuelve a enviar los aceptados. |

La bandeja mantiene los GET/PATCH de lectura. Las referencias `solicitud_id`,
`presupuesto_id` y `repuesto_id` son anulables. `orden_id`/`vehiculo_id` también
pueden ser nulos para alertas de stock. Estos cambios se incluyen en 3.0.0,
antes de su publicación definitiva, y requieren actualizar el consumidor móvil.

Integración IV debe registrar el token FCM después del login y cuando Firebase
lo renueve; al cerrar sesión debe desactivar el registro propio. Al cambiar de
cuenta, registrar el token lo asigna al usuario actual; el worker comprueba el
destinatario antes de enviar y omite trabajos de la cuenta anterior. El push
incluye `evento_id`, `notificacion_id` y `orden_id`; para la información vigente
la app consulta la bandeja autenticada. No hay implementación del APK aquí.

## Estados de los canales y reintentos

`pendiente` → `procesando` → `aceptada`, `fallida`, `sin_configuracion` u
`omitida`. Sin dispositivo hay un registro informativo `sin_dispositivo`.
Cada envío real conserva su propio intento antes de acceder al proveedor. Una
concesión temporal evita que dos workers reclamen simultáneamente el trabajo;
si vence, se conserva el intento interrumpido y puede recuperarse.

**Aceptada significa que SMTP/FCM confirmó la recepción**, no que la persona lo
leyó o que el dispositivo lo mostró. La lectura de la bandeja es independiente.
Un timeout después de que el proveedor recibió el mensaje puede producir otro
mensaje al reintentar: no se promete entrega exactamente una vez en SMTP/FCM.
El aviso lógico en la bandeja se conserva una sola vez. El correo usa Message-ID
estable por evento. Un token que FCM declara UNREGISTERED se desactiva.

Los avisos históricos no se reencolan automáticamente al migrar. Tampoco se
corrigen fechas históricas ni se cancelan órdenes existentes.

## Ejecución y despliegue

Migrar MS1 a `0008_contexto_avisos_ms1` (incluye tablas de 0007) y MS3 a
`0011_avisos_ms3`, además de las migraciones de órdenes ya documentadas. Son
cambios aditivos; no ejecutar en un destino compartido sin revisar primero sus
versiones y datos. El downgrade de MS1 se detiene si existen avisos sin orden.

Los workers continuos se activan con `MS1_NOTIFICATION_WORKER_ENABLED=true`
y `MS3_EVENT_WORKER_ENABLED=true`. Requieren procesos persistentes. Para un
scheduler externo se proporcionan, desde backend:

```sh
SGTM_ENV_FILE=ruta-privada python scripts/procesar_notificaciones.py --una-vez
SGTM_ENV_FILE=ruta-privada python scripts/publicar_avisos_ms3.py --una-vez
```

Cada llamada procesa como máximo un trabajo; se necesita frecuencia/capacidad
adecuada para vaciar la cola. **Un background task de FastAPI no garantiza
progreso en un despliegue serverless inactivo**. Antes de anunciar envío en el
ambiente evaluado, definir y verificar el worker/scheduler de ese ambiente.
Las rutas inversas usan la URL HTTP del mismo despliegue, sin crear bindings
cíclicos de Vercel. Eso no configura secretos ni proveedores.

## Proveedores

SMTP usa STARTTLS o SSL con validación de certificados. El contexto conserva
las CA del sistema y agrega las CA públicas de `certifi`, para funcionar también
en instalaciones de Python de macOS sin almacén de certificados configurado.
Nunca desactiva la verificación del certificado ni del nombre del servidor. Las variables están en
`.env.example`: `MS1_SMTP_HOST`, `MS1_SMTP_PORT`, `MS1_SMTP_MODO`,
`MS1_SMTP_REMITENTE`, `MS1_SMTP_USUARIO`, `MS1_SMTP_CLAVE`.
`sin_tls_local` se admite exclusivamente en loopback para Mailpit.

El Gmail institucional propuesto **no está conectado**. Debe autorizarse el uso
de la cuenta y comprobar qué permite el administrador de Google Workspace.
Este adaptador usa autenticación SMTP; no implementa OAuth de Gmail. No utilizar
la contraseña habitual en el chat o en Git. Si la organización no permite una
credencial SMTP específica, elegir un proveedor autorizado o implementar OAuth
como trabajo separado. Conviene una cuenta del equipo para el despliegue final.

FCM usa HTTP v1, OAuth de cuenta de servicio, `MS1_FCM_PROJECT_ID` y un archivo
privado señalado por `MS1_FCM_CREDENTIALS_FILE`. El JSON privado no pertenece a
Git. El proyecto, los permisos y los tokens/dispositivos deben configurarse y
validarse con Integración IV. Sin proveedor, el resultado es sin_configuracion,
sin éxito ficticio. Las pruebas automatizadas del adaptador FCM usan simulación.

## Demostración local y comprobaciones

`python scripts/demo_final.py infra` incluye Mailpit aislado:
SMTP `127.0.0.1:1026`, consola `http://127.0.0.1:8026` y remitente ficticio.
Captura mensajes localmente y no envía correos a Gmail ni a destinatarios externos.
La web está en `http://127.0.0.1:5383`. No usa ni borra los datos anteriores.

Pruebas: `test_canales_notificaciones.py`, `test_proveedores_notificaciones.py`,
`test_avisos_ms3_receptor.py`, `test_destinatario_notificaciones_ms2.py` y
`services/ms3_presupuestos/tests/test_avisos_transaccionales.py`. La suite de
integridad migra bases descartables y compara modelos, índices y claves.
El ejecutor `python scripts/verificar_backend.py` aísla PostgreSQL y usa buckets
exclusivos para las pruebas reales de MS4. El correo local y el navegador se
validan con los servicios de la demostración, sin acreditar Gmail/FCM externos.
