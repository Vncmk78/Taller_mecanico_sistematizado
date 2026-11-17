# 05 — API para la app móvil

Este es el documento de integración para el **equipo de app móvil**. Todo lo que
la app necesita pasa por la **Gateway**; nunca se llama a los microservicios
directamente.

---

## 1. URL base

```text
https://api-tallerconnect.inf.uct.cl
```

- Todos los endpoints de negocio empiezan con `/api/`.
- Solo HTTPS. El certificado es válido y no requiere configuración especial.
- No hay versión en la ruta (`/v1`): la API es la vigente.
- Documentación interactiva: <https://api-tallerconnect.inf.uct.cl/docs>
- Especificación OpenAPI (para generar clientes): <https://api-tallerconnect.inf.uct.cl/openapi.json>

> La app **no** debe usar los dominios `msN-tallerconnect...`: son solo para
> diagnóstico. La Gateway aplica CORS, límites de tamaño, timeouts y
> trazabilidad.

---

## 2. Autenticación

### 2.1 Login

```http
POST /api/auth/login
Content-Type: application/json
```

```json
{
  "email": "cliente@pruebas.cl",
  "password": "ClientePrueba123!"
}
```

Respuesta `200`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "cliente@pruebas.cl",
    "full_name": "Cliente de Prueba",
    "roles": ["cliente"],
    "is_active": true
  }
}
```

Notas:

- El token es un **JWT HS256** y dura **60 minutos**
  (`MS1_JWT_EXPIRE_MINUTES=60`). La respuesta **no** incluye `expires_in`; la app
  debe asumir 60 minutos o leer el claim `exp` del token.
- No hay refresh token. Al expirar, la app debe volver a pedir login (o guardar
  credenciales de forma segura y reintentar).
- Enviar el token en **todas** las peticiones:

```http
Authorization: Bearer <access_token>
```

- Tras **5 intentos fallidos consecutivos**, la cuenta se bloquea **15 minutos**
  (`MS1_LOGIN_MAX_INTENTOS`, `MS1_LOGIN_BLOQUEO_MINUTOS`). Mientras dure el
  bloqueo, el login responde `429` con la cabecera `Retry-After` (segundos
  restantes). Un login correcto reinicia el contador.

### 2.2 Registro de cliente

```http
POST /api/auth/register
Content-Type: application/json
```

```json
{
  "email": "nuevo@cliente.cl",
  "password": "Minimo8Caracteres",
  "full_name": "Nombre Apellido"
}
```

El rol `cliente` se asigna en el servidor. Los roles `mecanico` y
`administrador` **no** se pueden autoasignar: los otorga un administrador.

### 2.3 Usuario actual

```http
GET /api/auth/me
```

Devuelve el mismo objeto `user` del login. Útil para validar el token al abrir la
app.

---

## 3. Convenciones de la API

### 3.1 Formato de datos

- JSON con `Content-Type: application/json` (excepto la subida de evidencias,
  que es `multipart/form-data`).
- Fechas en **UTC ISO-8601** con sufijo `Z`:
  `"2026-11-15T05:41:45.874290Z"`.
- Dinero como **string decimal**: `"23990.00"` (no usar `float` para sumar).
- IDs numéricos enteros, salvo `evidencia_id` y `dispositivo_id`, que son
  **UUID** en string.

### 3.2 Paginación

Los listados operativos de MS1, MS2 y MS4 comparten un contrato de **arreglo
plano paginado**:

```http
GET /api/vehiculos?limite=50&desde=0
```

```json
[ { ... }, { ... } ]
```

- `limite`: registros por página, entero entre **1 y 100** (por defecto 50).
- `desde`: desplazamiento, entero **≥ 0** (por defecto 0).
- El total de registros (antes de paginar) viaja en la cabecera
  **`X-Total-Count`**; la Gateway la expone por CORS.
- Un valor fuera de rango responde `422`.

Endpoints que siguen este contrato:

| Servicio | Rutas |
| --- | --- |
| MS1 | `/api/auth/usuarios`, `/api/notificaciones/dispositivos`, `/api/notificaciones/{id}/entregas` |
| MS2 | `/api/vehiculos`, `/api/vehiculos/asignados`, `/api/ordenes`, `/api/ordenes/{id}/historial`, `/api/ordenes/{id}/bitacora`, `/api/ordenes/cancelaciones/pendientes` |
| MS4 | `/api/evidencias` |

Casos particulares:

- `/api/notificaciones` conserva `limite`/`offset` y sus cabeceras propias
  (`X-Notificaciones-Total`, `X-Notificaciones-No-Leidas`).
- `/api/ordenes/vehiculo/{id}/historial` mantiene `limit`/`offset` y acepta
  `limite`/`desde` como alias canónicos.

La app móvil recorre todas las páginas con `limite=100` y `X-Total-Count`, de
modo que cada pantalla recibe la colección completa y pagina en el cliente
(6/12/24). Así el comportamiento es el mismo en todos los listados.

**Objeto paginado** — MS3 (presupuestos, repuestos, proveedores, inventario):

```json
{
  "total": 4,
  "desde": 0,
  "limite": 50,
  "presupuestos": [ ... ]
}
```

El nombre de la colección cambia según el recurso (`presupuestos`, `repuestos`,
`proveedores`, `movimientos`).

Parámetros típicos de MS3: `limite` (máximo 200), `desde` y filtros propios del
recurso (`orden_id`, `estado`, `texto`, etc.). Consultar `/docs` para cada caso.

### 3.3 Errores

Formato uniforme:

```json
{ "detail": "No autenticado" }
```

o, en errores de validación (422), una lista:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "orden_id"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

| Código | Significado |
| --- | --- |
| 400 | Petición mal formada |
| 401 | Sin token, token vencido o inválido |
| 403 | Autenticado, pero sin permiso para esa operación |
| 404 | El recurso no existe o no es visible para el usuario |
| 409 | Conflicto con el estado actual (orden cerrada, cancelación bloqueada) |
| 413 | Archivo demasiado grande |
| 415 | Formato de archivo no permitido |
| 422 | Datos inválidos o regla de negocio incumplida |
| 429 | Demasiados intentos de login; ver cabecera `Retry-After` |
| 503 | Un servicio interno o el almacenamiento no está disponible |

Mensajes reales:

```json
{ "detail": "No autenticado" }
{ "detail": "No tienes permiso para realizar esta operación" }
{ "detail": "Orden no encontrada" }
{ "detail": "Evidencia no encontrada" }
```

Los errores `502`, `503` y `504` incluyen la cabecera `Retry-After` con los
segundos sugeridos antes de reintentar. Todas las respuestas incluyen
`X-Request-ID` para trazabilidad.

### 3.4 CORS

La Gateway solo autoriza el origen `https://tallerconnect.inf.uct.cl`. Una app
nativa **no envía** cabecera `Origin`, así que no se ve afectada. Si se usa un
**WebView**, cargar la app desde el dominio web o evitar peticiones con `Origin`
distinto: un origen ajeno recibe `400`.

---

## 4. Catálogo de endpoints

La API tiene **94 operaciones** sobre **75 rutas**. Las marcadas con 📱 son las
que normalmente usa la app móvil.

### 4.1 Autenticación

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST 📱 | `/api/auth/login` | Iniciar sesión |
| POST 📱 | `/api/auth/register` | Registrar cliente |
| GET 📱 | `/api/auth/me` | Usuario actual |

### 4.2 Usuarios (administrador)

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/auth/usuarios` | Listar todos los usuarios |
| GET | `/api/auth/usuarios/{usuario_id}` | Consultar un usuario |
| POST | `/api/auth/usuarios/{usuario_id}/roles` | Asignar rol restringido |
| DELETE | `/api/auth/usuarios/{usuario_id}/roles/{rol}` | Retirar rol restringido |

### 4.3 Clientes

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/clientes/perfil` | Consultar mi perfil de cliente |
| POST 📱 | `/api/clientes/perfil` | Crear/actualizar mi perfil de cliente |

### 4.4 Vehículos

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/vehiculos` | Listar vehículos visibles |
| POST 📱 | `/api/vehiculos` | Registrar un vehículo |
| GET 📱 | `/api/vehiculos/{vehiculo_id}` | Consultar un vehículo |
| PATCH 📱 | `/api/vehiculos/{vehiculo_id}` | Actualizar parcialmente un vehículo |
| GET 📱 | `/api/vehiculos/asignados` | Vehículos asignados al mecánico |

### 4.5 Órdenes de trabajo

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/ordenes` | Listar órdenes visibles |
| POST | `/api/ordenes` | Crear una orden (administrador) |
| GET 📱 | `/api/ordenes/{orden_id}` | Consultar una orden |
| GET 📱 | `/api/ordenes/{orden_id}/historial` | Historial de estados |
| GET 📱 | `/api/ordenes/{orden_id}/bitacora` | Bitácora de trabajo |
| POST 📱 | `/api/ordenes/{orden_id}/bitacora` | Registrar observación/acción |
| PUT | `/api/ordenes/{orden_id}/mecanico` | Asignar o reasignar mecánico |
| PATCH 📱 | `/api/ordenes/{orden_id}/estado` | Cambiar estado (solo `5 → 6`) |
| POST | `/api/ordenes/{orden_id}/entrega` | Registrar entrega física |
| POST 📱 | `/api/ordenes/{orden_id}/cancelacion` | Solicitar cancelación |
| POST | `/api/ordenes/{orden_id}/cancelacion/confirmacion` | Confirmar cancelación |
| POST | `/api/ordenes/{orden_id}/devolucion` | Registrar devolución física |
| GET | `/api/ordenes/cancelaciones/pendientes` | Cancelaciones pendientes |
| GET 📱 | `/api/ordenes/vehiculo/{vehiculo_id}/historial` | Órdenes por vehículo |
| POST 📱 | `/api/ordenes/{orden_id}/nueva-atencion` | Solicitar nueva atención |
| GET 📱 | `/api/ordenes/nuevas-atenciones` | Listar solicitudes |
| GET 📱 | `/api/ordenes/nuevas-atenciones/{solicitud_id}` | Ver una solicitud |
| POST | `/api/ordenes/nuevas-atenciones/{solicitud_id}/revision` | Aceptar/rechazar |
| POST | `/api/ordenes/nuevas-atenciones/{solicitud_id}/orden` | Generar orden nueva |
| GET | `/api/ordenes/configuracion/capacidad/ingresos-diarios` | Cupo diario |
| PUT | `/api/ordenes/configuracion/capacidad/ingresos-diarios` | Configurar cupo |
| GET | `/api/ordenes/configuracion/capacidad/mecanicos` | Capacidad por mecánico |
| PUT | `/api/ordenes/configuracion/capacidad/mecanicos` | Configurar capacidad |
| POST | `/api/ordenes/{orden_id}/envios-presupuesto` | Aplicar envío verificado (interno) |
| POST | `/api/ordenes/{orden_id}/decisiones-presupuesto` | Aplicar decisión (interno) |

> Los dos últimos son **internos** entre MS2 y MS3. La app no los llama: usa los
> endpoints de presupuestos.

### 4.6 Presupuestos

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/presupuestos` | Listar o buscar el de una orden (`?orden_id=`) |
| POST 📱 | `/api/presupuestos` | Crear presupuesto de una orden (mecánico/admin) |
| GET 📱 | `/api/presupuestos/{presupuesto_id}` | Detalle con todas las versiones |
| POST | `/api/presupuestos/{presupuesto_id}/versiones` | Crear versión siguiente |
| PUT | `/api/presupuestos/{presupuesto_id}/versiones/{numero}/items` | Reemplazar ítems en borrador |
| POST 📱 | `/api/presupuestos/{presupuesto_id}/versiones/{numero}/envio` | Enviar al cliente |
| POST 📱 | `/api/presupuestos/{presupuesto_id}/versiones/{numero}/decision` | Aprobar o rechazar |
| GET 📱 | `/api/presupuestos/{presupuesto_id}/versiones/{numero}` | Ver una versión |
| POST | `/api/presupuestos/{presupuesto_id}/modificacion` | Modificar aprobado (nueva versión) |
| GET | `/api/presupuestos/{presupuesto_id}/envio-inicial` | Verificar envío inicial |
| POST | `/api/presupuestos/{presupuesto_id}/envio-inicial/aplicacion` | Reintentar envío |
| GET | `/api/presupuestos/decisiones/{decision_id}` | Consultar decisión |
| POST | `/api/presupuestos/decisiones/{decision_id}/aplicacion` | Reintentar decisión |
| GET | `/api/presupuestos/ordenes/{orden_id}/primera-aprobacion` | ¿Tiene aprobación inicial? |

### 4.7 Repuestos y proveedores

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/repuestos` | Listar o buscar repuestos |
| POST | `/api/repuestos` | Registrar repuesto |
| GET 📱 | `/api/repuestos/{repuesto_id}` | Detalle |
| PATCH | `/api/repuestos/{repuesto_id}` | Modificar |
| DELETE | `/api/repuestos/{repuesto_id}` | Eliminar si nunca se usó |
| GET | `/api/repuestos/{repuesto_id}/trazabilidad` | Trazabilidad repuesto→proveedor |
| GET | `/api/proveedores` | Listar o buscar proveedores |
| POST | `/api/proveedores` | Registrar proveedor |
| GET | `/api/proveedores/{proveedor_id}` | Detalle con sus repuestos |
| PATCH | `/api/proveedores/{proveedor_id}` | Modificar |
| DELETE | `/api/proveedores/{proveedor_id}` | Eliminar sin repuestos |
| GET | `/api/proveedores/{proveedor_id}/trazabilidad` | Repuestos que abastece |

### 4.8 Inventario

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/inventario/stock/{repuesto_id}` | Stock físico, comprometido y disponible |
| GET | `/api/inventario/alertas` | Repuestos bajo umbral |
| POST | `/api/inventario/movimientos` | Registrar movimiento de stock |
| GET | `/api/inventario/movimientos` | Movimientos recientes |
| POST | `/api/inventario/disponibilidad` | Validar stock antes de usar |
| POST 📱 | `/api/inventario/ordenes/{orden_id}/reserva` | Reservar repuestos |
| POST 📱 | `/api/inventario/ordenes/{orden_id}/consumos` | Descontar repuestos usados |
| POST | `/api/inventario/ordenes/{orden_id}/liberacion` | Liberar reservas |
| GET | `/api/inventario/ordenes/{orden_id}/disponibilidad` | Validar stock faltante |
| POST | `/api/inventario/ordenes/{orden_id}/disponibilidad` | Confirmar y reservar |
| GET | `/api/inventario/umbral-general` | Umbral general vigente |
| PUT | `/api/inventario/umbral-general` | Configurar umbral general |
| GET | `/api/inventario/historial-umbral` | Cambios de umbral |

### 4.9 Evidencias

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST 📱 | `/api/evidencias` | Subir foto o video (`multipart/form-data`) |
| GET 📱 | `/api/evidencias?orden_id={id}` | Listar evidencias de una orden |
| GET 📱 | `/api/evidencias/{evidencia_id}` | Detalle de una evidencia |
| GET 📱 | `/api/evidencias/{evidencia_id}/descarga` | URL prefirmada de descarga |

### 4.10 Notificaciones

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET 📱 | `/api/notificaciones` | Mi bandeja |
| PATCH 📱 | `/api/notificaciones/{notificacion_id}/leer` | Marcar una como leída |
| PATCH 📱 | `/api/notificaciones/leer-todas` | Marcar todas como leídas |
| GET 📱 | `/api/notificaciones/{notificacion_id}/entregas` | Intentos de correo/push |
| POST 📱 | `/api/notificaciones/{notificacion_id}/reintentos` | Reintentar canales fallidos |
| GET 📱 | `/api/notificaciones/dispositivos` | Mis dispositivos |
| POST 📱 | `/api/notificaciones/dispositivos` | Registrar dispositivo push |
| DELETE 📱 | `/api/notificaciones/dispositivos/{dispositivo_id}` | Desactivar dispositivo |

### 4.11 Salud

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/health` | Salud de la Gateway |
| GET | `/api/health/servicios` | Salud de los 4 microservicios |
| GET | `/api/health/servicios/{servicio}` | Diagnóstico de un servicio |

---

## 5. Ejemplos reales por flujo

Todos los ejemplos se capturaron contra el ambiente de Kubero.

### 5.1 Listar vehículos

```http
GET /api/vehiculos
Authorization: Bearer <token>
```

```json
[
  {
    "vehiculo_id": 1,
    "cliente_id": 1,
    "patente": "ABCD12",
    "marca": "Toyota",
    "modelo": "Yaris",
    "anio": 2015,
    "kilometraje": 80000
  }
]
```

### 5.2 Listar órdenes

```http
GET /api/ordenes
Authorization: Bearer <token>
```

```json
[
  {
    "orden_id": 1,
    "vehiculo_id": 1,
    "ingreso_id": 1,
    "estado_codigo": 5,
    "mecanico_actual_id": 2,
    "creado_por_id": 3,
    "creado_en": "2026-11-15T04:35:51.358253Z",
    "actualizado_en": "2026-11-15T04:55:32.975771Z",
    "devuelto_en": null,
    "devuelto_por_id": null
  }
]
```

El cliente solo ve sus órdenes; el mecánico, las asignadas; el administrador,
todas.

### 5.3 Crear una orden (administrador)

```http
POST /api/ordenes
Authorization: Bearer <token admin>
Content-Type: application/json
```

```json
{ "vehiculo_id": 6 }
```

Respuesta `201`:

```json
{
  "orden_id": 6,
  "vehiculo_id": 6,
  "ingreso_id": 6,
  "estado_codigo": 1,
  "mecanico_actual_id": null,
  "creado_por_id": 3,
  "creado_en": "2026-11-15T05:41:44.816826Z",
  "actualizado_en": "2026-11-15T05:41:44.816826Z",
  "devuelto_en": null,
  "devuelto_por_id": null
}
```

### 5.4 Asignar mecánico

```http
PUT /api/ordenes/6/mecanico
Authorization: Bearer <token admin>
```

```json
{ "mecanico_id": 2 }
```

La orden pasa de `1` a `2`.

### 5.5 Crear un presupuesto (mecánico)

```http
POST /api/presupuestos
Authorization: Bearer <token mecánico>
Content-Type: application/json
```

```json
{
  "orden_id": 6,
  "items": [
    {
      "tipo": "repuesto",
      "descripcion": "Filtro de aceite Toyota",
      "cantidad": 1,
      "precio_unitario": 8990,
      "repuesto_id": 1
    },
    {
      "tipo": "mano_de_obra",
      "descripcion": "Cambio de aceite",
      "cantidad": 1,
      "precio_unitario": 15000
    }
  ]
}
```

Respuesta (resumida):

```json
{
  "presupuesto_id": 4,
  "orden_id": 6,
  "versiones": [
    { "numero": 1, "estado": "borrador", "total": "23990.00", "items": [ ... ] }
  ]
}
```

### 5.6 Enviar el presupuesto

```http
POST /api/presupuestos/4/versiones/1/envio
Authorization: Bearer <token admin>
```

```json
{
  "efecto_en_orden": "esperando_aprobacion",
  "aplicacion_en_orden": { "estado_aplicado": 3 }
}
```

La orden pasa a `3`. Se genera el aviso `presupuesto.enviado` para el cliente
(visible en su bandeja en pocos segundos).

### 5.7 Aprobar o rechazar (cliente)

```http
POST /api/presupuestos/4/versiones/1/decision
Authorization: Bearer <token cliente>
Content-Type: application/json
```

```json
{ "decision": "aprobado" }
```

```json
{
  "efecto_en_orden": "en_reparacion",
  "aplicacion_en_orden": { "estado_aplicado": 5 }
}
```

- `"aprobado"` → orden `5` (En reparación) si hay stock suficiente para los
  repuestos del presupuesto, o `4` (Esperando repuestos) si falta alguno.
- `"rechazado"` → orden `8` (Cancelado) y libera reservas.

### 5.8 Subir una evidencia (mecánico o administrador)

```http
POST /api/evidencias
Authorization: Bearer <token mecánico>
Content-Type: multipart/form-data
```

Campos del formulario:

| Campo | Tipo | Obligatorio | Valores |
| --- | --- | --- | --- |
| `archivo` | archivo | Sí | JPG, PNG, WEBP, MP4, MOV |
| `orden_id` | entero | Sí | Orden de trabajo |
| `contexto` | texto | Sí | `diagnostico`, `presupuesto`, `reparacion`, `resultado_final` |
| `presupuesto_id` | entero | Solo si `contexto=presupuesto` | Debe pertenecer a la orden |
| `visible_cliente` | booleano | No | Por defecto lo decide el contexto |

Ejemplo con `curl`:

```bash
curl -X POST https://api-tallerconnect.inf.uct.cl/api/evidencias \
  -H "Authorization: Bearer $TOKEN" \
  -F "archivo=@foto.jpg" \
  -F "orden_id=1" \
  -F "contexto=reparacion" \
  -F "visible_cliente=true"
```

Respuesta `201`:

```json
{
  "evidencia_id": "4f6dcb48-d629-4c8c-8658-1668cd320794",
  "orden_id": 1,
  "presupuesto_id": null,
  "contexto": "reparacion",
  "tipo_archivo": "foto",
  "visible_cliente": true,
  "estado": "confirmada",
  "nombre_original": "foto.jpg",
  "content_type": "image/jpeg",
  "tamano_bytes": 84512,
  "creada_en": "2026-11-15T05:28:36.600849Z"
}
```

Reglas:

- La orden no puede estar **entregada** ni **cancelada** (`409`).
- El cliente **no** puede subir evidencias (`403`).
- El archivo se valida por **contenido real**, no solo por extensión (`415` si no
  coincide).
- **Límite efectivo en la Gateway: 12 MiB por petición** (no 100 MiB, aunque el
  servicio acepte videos más grandes). Para videos grandes hay que subirlos por
  partes o subir solo clips cortos.

### 5.9 Descargar una evidencia

```http
GET /api/evidencias/4f6dcb48-d629-4c8c-8658-1668cd320794/descarga
Authorization: Bearer <token>
```

```json
{
  "url": "https://ms4-tallerconnect.inf.uct.cl/evidencias/ordenes/1/4f6dcb48...png?X-Amz-Algorithm=...&X-Amz-Expires=300&X-Amz-Signature=...",
  "expira_en": 300
}
```

- La URL es **prefirmada** y dura **300 segundos**.
- Se descarga **sin** cabecera `Authorization` (la firma va en la URL).
- `content_type` y `Content-Disposition` viajan firmados: la app debe usar la URL
  tal cual, sin modificarla.

### 5.10 Bandeja de notificaciones

```http
GET /api/notificaciones?limite=20&solo_no_leidas=false&offset=0
Authorization: Bearer <token>
```

Los totales vienen en **cabeceras**:

```text
X-Notificaciones-Total: 28
X-Notificaciones-No-Leidas: 3
```

Cuerpo:

```json
[
  {
    "notificacion_id": 51,
    "tipo": "nueva_atencion.solicitada",
    "orden_id": 3,
    "vehiculo_id": 3,
    "titulo": "Solicitud de nueva atención pendiente",
    "mensaje": "El Cliente solicitó una nueva atención (solicitud n° 1, orden cancelada n° 3). Revísela en Nuevas atenciones.",
    "ocurrido_en": "2026-11-15T05:44:26.467687Z",
    "creado_en": "2026-11-15T05:44:27.279310Z",
    "leida": false,
    "leida_en": null,
    "solicitud_id": 1,
    "presupuesto_id": null,
    "repuesto_id": null
  }
]
```

Marcar como leída devuelve `204` sin cuerpo:

```http
PATCH /api/notificaciones/51/leer
```

```http
PATCH /api/notificaciones/leer-todas
```

### 5.11 Registrar el dispositivo para push

```http
POST /api/notificaciones/dispositivos
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "token": "fcm-token-del-dispositivo",
  "plataforma": "android"
}
```

Respuesta `201`:

```json
{
  "dispositivo_id": "3194cb93-e7f9-4a55-9f73-40d947880d98",
  "plataforma": "android",
  "activo": true,
  "creado_en": "2026-11-15T05:44:26.169310Z",
  "actualizado_en": "2026-11-15T05:44:26.169310Z"
}
```

Para desactivar:

```http
DELETE /api/notificaciones/dispositivos/3194cb93-e7f9-4a55-9f73-40d947880d98
```

Devuelve `204`.

> Hoy **no hay proyecto FCM configurado** en el servidor. La app puede registrar
> el token y la bandeja funciona; las entregas push quedan como
> `sin_dispositivo` o `pendiente`. Ver
> [08 — Pendientes](08-pendientes-y-deuda.md).

### 5.12 Nueva atención

```http
POST /api/ordenes/3/nueva-atencion
Authorization: Bearer <token cliente>
```

```json
{ "descripcion": "Quiero retomar la reparación con otro presupuesto" }
```

```json
{
  "solicitud_id": 1,
  "orden_cancelada_id": 3,
  "vehiculo_id": 3,
  "cliente_usuario_id": 1,
  "descripcion": "Quiero retomar la reparación con otro presupuesto",
  "solicitada_en": "2026-11-15T05:44:26.467687Z",
  "situacion": "pendiente",
  "respuesta": null,
  "revisor_id": null,
  "revisada_en": null,
  "orden_generada_id": null
}
```

El administrador revisa:

```http
POST /api/ordenes/nuevas-atenciones/1/revision
```

```json
{ "decision": "aceptada", "respuesta": "Aceptada, coordinaremos una nueva evaluación" }
```

Y genera la orden:

```http
POST /api/ordenes/nuevas-atenciones/1/orden
```

```json
{
  "solicitud": { "situacion": "aceptada", "orden_generada_id": 7 },
  "orden": { "orden_id": 7, "estado_codigo": 1 }
}
```

---

## 6. Flujo recomendado para la app

```text
Arranque
  └─ ¿Hay token guardado? ──no──► Login
        │sí
        ▼
  GET /api/auth/me  ──401──► Login
        │200
        ▼
  Guardar user + roles en estado global
        │
        ├─ rol cliente      → vehículos, órdenes propias, presupuestos, evidencias visibles
        ├─ rol mecánico     → órdenes asignadas, bitácora, presupuesto, evidencias, inventario
        └─ rol administrador→ todo + capacidad, proveedores, repuestos, notificaciones
        │
        ▼
  POST /api/notificaciones/dispositivos (una vez por sesión/dispositivo)
        │
        ▼
  GET /api/notificaciones (al abrir y al recibir push)
```

Recomendaciones:

1. **Guardar el token** en almacenamiento seguro (Keychain / Keystore).
2. **No cachear** listados críticos más de unos segundos: el estado de una orden
   cambia con las acciones de otros roles.
3. **Reintentar** `GET` ante `502`, `503` o `504` respetando la cabecera
   `Retry-After` que envía la Gateway (segundos sugeridos).
4. **No reintentar** automáticamente `POST`/`PATCH` de negocio sin idempotencia:
   un `POST /api/ordenes` repetido crea dos órdenes.
5. **Mostrar los códigos de estado** con el mapa de la sección 7.
6. Para dinero, usar decimal (no `float`) y respetar el string de la API.

---

## 7. Mapa de estados de una orden

| Código | Nombre para la app |
| --- | --- |
| 1 | Recibido |
| 2 | Esperando diagnóstico |
| 3 | Esperando aprobación del presupuesto |
| 4 | Esperando repuestos |
| 5 | En reparación |
| 6 | Listo para entrega |
| 7 | Entregado |
| 8 | Cancelado |

Los estados `7` y `8` son **terminales**: no admiten más acciones.

---

## 8. Consultar la API sin la app

- **Swagger UI:** <https://api-tallerconnect.inf.uct.cl/docs> → botón
  *Authorize* → pegar el `access_token`.
- **OpenAPI JSON:** <https://api-tallerconnect.inf.uct.cl/openapi.json> → sirve
  para generar un cliente tipado (Kotlin, Swift, Dart, etc.).
- **Health:** <https://api-tallerconnect.inf.uct.cl/api/health/servicios> para
  saber si el problema es de la app o del backend.

---

## 9. Preguntas frecuentes del equipo móvil

**¿Por qué recibo 401 si acabo de hacer login?**
El token dura 60 minutos. Si la app estuvo en segundo plano mucho tiempo, hay que
volver a autenticarse.

**¿Por qué recibo 404 en una orden que existe?**
La API no revela la existencia de recursos que no son visibles para el usuario.
Un cliente solo ve sus órdenes; un mecánico, las asignadas.

**¿Por qué falla la subida de un video de 30 MB?**
La Gateway corta el cuerpo en **12 MiB**. Es una decisión de seguridad del
despliegue, no un error de la app.

**¿Puedo usar HTTP en vez de HTTPS?**
No. El ambiente solo responde por HTTPS.

**¿La app necesita CORS?**
No. CORS es del navegador. Solo afecta si se usa un WebView con un origen
distinto al dominio web.
