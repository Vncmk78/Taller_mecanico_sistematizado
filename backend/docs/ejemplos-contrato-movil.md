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

## 3. Consultar historial de órdenes de un vehículo

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

## 4. Estados de la orden

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

## 5. Errores y compatibilidad

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
