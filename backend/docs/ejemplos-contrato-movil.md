# Ejemplos de contrato para la aplicación móvil

La aplicación móvil consume únicamente la API Gateway. Las rutas de los
ejemplos se exponen allí bajo el prefijo `/api`; no debe conectarse directamente
a MS1 o MS2.
Los identificadores y tokens de este documento son ficticios.

## 1. Iniciar sesión

```http
POST /api/auth/login
Content-Type: application/json
```

```json
{
  "email": "ana@correo.cl",
  "password": "<contraseña ingresada por la persona>"
}
```

Respuesta `200`:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 7,
    "email": "ana@correo.cl",
    "full_name": "Ana Pérez",
    "roles": ["cliente"],
    "is_active": true
  }
}
```

Enviar el token en cada solicitud protegida como
`Authorization: Bearer <access_token>`. `roles` es siempre una lista; no leer
un campo singular `role`. Si el JWT falta o no es válido, la Gateway devuelve
`401`.

## 2. Consultar vehículos del cliente

```http
GET /api/vehiculos
Authorization: Bearer <jwt>
```

Respuesta `200`:

```json
[
  {
    "vehiculo_id": 12,
    "patente": "AB1234",
    "marca": "Toyota",
    "modelo": "Corolla",
    "anio": 2018,
    "kilometraje": 45000
  }
]
```

Un cliente recibe solo sus vehículos. El endpoint también está disponible
para Administrador, que ve todos. Mecánico debe consultar
`GET /api/vehiculos/asignados`, que lista vehículos con órdenes actualmente
asignadas a ese mecánico.

## 3. Listar órdenes del mecánico y consultar su detalle

```http
GET /api/ordenes
Authorization: Bearer <jwt del mecánico>
```

MS2 obtiene la identidad desde el JWT y devuelve solo las órdenes actualmente
asignadas al Mecánico. No se envía un `mecanico_id` elegido por la aplicación.
Administrador puede ver todas y Cliente solo las de sus vehículos. Una lista
vacía válida responde `200 []`; un `500` nunca debe interpretarse como lista
vacía.

Ejemplo de respuesta `200`:

```json
[
  {
    "orden_id": 31,
    "vehiculo_id": 12,
    "ingreso_id": 18,
    "estado_codigo": 5,
    "mecanico_actual_id": 50,
    "creado_por_id": 99,
    "creado_en": "2026-09-28T10:30:00-03:00",
    "actualizado_en": "2026-09-28T12:35:00-03:00"
  }
]
```

Para abrir esa orden:

```http
GET /api/ordenes/31
Authorization: Bearer <jwt del mecánico>
```

Devuelve `200` con el objeto de orden (sin la lista). Una orden inexistente o
ajena devuelve `404`. La aplicación debe usar `orden_id` para abrir el detalle
y `estado_codigo` para interpretar el catálogo de estados.

## 4. Consultar historial de órdenes de un vehículo

```http
GET /api/ordenes/vehiculo/12/historial?limit=20&offset=0
Authorization: Bearer <jwt>
```

Respuesta `200`:

```json
{
  "items": [
    {
      "orden_id": 31,
      "vehiculo_id": 12,
      "ingreso_id": 18,
      "estado_codigo": 6,
      "mecanico_actual_id": 50,
      "creado_por_id": 99,
      "creado_en": "2026-09-28T10:30:00-03:00",
      "actualizado_en": "2026-09-28T12:35:00-03:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

`limit` va de 1 a 100 (por defecto 20) y `offset` es un entero desde 0 (por
defecto 0). El orden es descendente por creación y luego por `orden_id`. Si el
cliente consulta su vehículo sin órdenes, recibe `200` y `items: []`. Un
vehículo inexistente o fuera del alcance del rol devuelve `404`.

El endpoint aplica alcance según el rol: Cliente ve órdenes de vehículos
propios; Mecánico solo órdenes actualmente asignadas a él; Administrador ve
cualquier vehículo existente. El cliente móvil debe poder tratar el mismo
`404` para recurso inexistente y recurso sin autorización.

## 5. Estados de la orden

`estado_codigo` es un código entero del catálogo de MS2, no texto libre:

| Código | Estado |
| --- | --- |
| 1 | Recibido |
| 2 | Esperando diagnóstico |
| 3 | Esperando aprobación de presupuesto |
| 4 | Esperando repuestos |
| 5 | En reparación |
| 6 | Listo |
| 7 | Entregado |
| 8 | Cancelado |

La interfaz puede mapear el código a una etiqueta traducible. No debe inferir
que cualquier código puede asignarse directamente ni intentar cambiar el
estado desde el cliente: MS2 valida transiciones y hechos de negocio; usar la
operación específica documentada para cada acción. `Entregado` y `Cancelado`
son terminales.

## 6. Finalizar el trabajo del mecánico

Cuando la orden está `En reparación` (`estado_codigo=5`), el Mecánico asignado
puede registrar que quedó `Listo` (`6`):

```http
PATCH /api/ordenes/31/estado
Authorization: Bearer <jwt del mecánico asignado>
Content-Type: application/json
```

```json
{
  "estado_destino": 6,
  "observacion": "Trabajo autorizado finalizado"
}
```

La respuesta `200` conserva el contrato de orden con `estado_codigo=6`; MS2
guarda el actor autenticado y el cambio en el historial dentro de la misma
transacción. Sin el rol o la asignación requeridos responde `403`; si la
transición no corresponde al estado actual, `409`.

No existe una actualización genérica `PUT/PATCH /api/ordenes/{orden_id}`.
Asignación, decisiones de presupuesto, entrega y cancelación tienen operaciones
específicas en el contrato completo. No enviar el objeto de orden completo ni
atribuir el cambio con un actor elegido por la aplicación.

## 7. Errores y compatibilidad

- `401`: sesión ausente, expirada o inválida; renovar/iniciar sesión según el
  flujo de la aplicación.
- `403`: el rol no puede realizar la acción.
- `404`: recurso inexistente o no visible para la identidad; no revelar cuál
  condición ocurrió.
- `422`: parámetros/body no cumplen el esquema; la respuesta incluye detalles
  de validación.
- `502`: un microservicio requerido no está disponible; no tratarlo como una
  respuesta vacía.

Los campos de fechas son ISO 8601 e incluyen zona horaria. Los IDs son enteros
positivos. Para actualizar un contrato, revisar `/docs` de la Gateway y acordar
el cambio con Integración II antes de depender de campos nuevos en el cliente.

## Referencias

- Contrato completo: [`contratos-api-gateway.md`](contratos-api-gateway.md).
- Máquina de estados, eventos disponibles y operaciones bloqueadas:
  [`maquina-estados-ordenes.md`](maquina-estados-ordenes.md).
