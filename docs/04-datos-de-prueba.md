# 04 — Datos de prueba del ambiente

Este documento describe **exactamente** lo que hay hoy en la base del ambiente de
Kubero, para que QA y el equipo de app móvil puedan probar sin crear todo desde
cero.

> **Última verificación:** 15 de noviembre de 2026.
> Estos datos viven en las bases PostgreSQL del clúster, **no** en el
> repositorio. Si se reconstruye el ambiente, hay que volver a crearlos (el seed
> de usuarios es automático; el resto se crea por API).

---

## 1. Cuentas de demostración

Todas las cuentas están activas y usan contraseñas de prueba. **No dan acceso a
infraestructura**: solo a la aplicación.

| ID | Correo | Contraseña | Roles |
| --- | --- | --- | --- |
| 1 | `cliente@pruebas.cl` | `ClientePrueba123!` | cliente |
| 2 | `mecanico@pruebas.cl` | `MecanicoPrueba123!` | mecanico |
| 3 | `administrador@pruebas.cl` | `AdminPrueba123!` | administrador |
| 4 | `cliente-mecanico@pruebas.cl` | `ClienteMecanicoPrueba123!` | cliente, mecanico |
| 5 | `cliente-administrador@pruebas.cl` | `ClienteAdministradorPrueba123!` | cliente, administrador |
| 6 | `mecanico-administrador@pruebas.cl` | `MecanicoAdministradorPrueba123!` | mecanico, administrador |
| 7 | `cliente-mecanico-administrador@pruebas.cl` | `ClienteMecanicoAdministradorPrueba123!` | cliente, mecanico, administrador |
| 8 | `tecnico.prueba@pruebas.cl` | `TecnicoPrueba123!` | cliente |

Las cuentas 4–7 existen para probar **usuarios con más de un rol**: la misma
persona puede actuar como cliente y como mecánico, por ejemplo.

> Las contraseñas 4–7 están definidas en el script de seed
> (`backend/scripts/seed_usuarios_prueba.py`). Si alguna no coincide, revisar ese
> archivo antes de asumir un problema del ambiente.

### Cómo se crearon

```bash
python backend/scripts/seed_usuarios_prueba.py
```

El script es **idempotente**: si la cuenta existe, actualiza nombre y roles; si no,
la crea. Requiere acceso a la base de MS1 y al secreto JWT.

---

## 2. Vehículos

Todos pertenecen al usuario **1** (`cliente@pruebas.cl`).

| ID | Patente | Marca | Modelo | Año | Kilometraje |
| --- | --- | --- | --- | --- | --- |
| 1 | `ABCD12` | Toyota | Yaris | 2015 | 80.000 |
| 2 | `EFGH34` | Nissan | Versa | 2019 | 45.000 |
| 3 | `IJKL56` | Hyundai | Accent | 2021 | 20.000 |
| 4 | `MNOP78` | Kia | Rio | 2017 | 120.000 |
| 5 | `QRST90` | Chevrolet | Sail | 2018 | 60.000 |
| 6 | `UVWX12` | Suzuki | Swift | 2020 | 30.000 |

---

## 3. Órdenes de trabajo

| Orden | Vehículo | Estado | Código | Mecánico | Qué representa |
| --- | --- | --- | --- | --- | --- |
| 1 | `ABCD12` | En reparación | 5 | 2 | Flujo completo con evidencia y presupuesto aprobado |
| 2 | `EFGH34` | Entregado | 7 | 2 | Orden cerrada con éxito |
| 3 | `IJKL56` | Cancelado | 8 | 2 | Presupuesto **rechazado** por el cliente |
| 4 | `MNOP78` | Cancelado | 8 | — | Cancelación administrativa (sin mecánico) |
| 5 | `QRST90` | Esperando diagnóstico | 2 | 2 | Orden asignada, aún sin presupuesto |
| 6 | `UVWX12` | En reparación | 5 | 2 | Flujo de notificaciones de presupuesto (aviso enviado + decidido) |
| 7 | `IJKL56` | Recibido | 1 | — | Generada desde una **solicitud de nueva atención** |

Estados: `1` Recibido · `2` Esperando diagnóstico · `3` Esperando aprobación ·
`4` Esperando repuestos · `5` En reparación · `6` Listo · `7` Entregado ·
`8` Cancelado.

### Historial de la orden 1 (ejemplo real)

| # | De | A | Actor | Cuándo (UTC) |
| --- | --- | --- | --- | --- |
| 1 | — | 1 | admin (3) | 2026-11-15 04:35:51 |
| 2 | 1 | 2 | admin (3) | 2026-11-15 04:55:11 |
| 3 | 2 | 3 | admin (3) | 2026-11-15 04:55:22 |
| 4 | 3 | 5 | cliente (1) | 2026-11-15 04:55:32 |

---

## 4. Presupuestos

| Presupuesto | Orden | Versiones | Total | Estado | Versión vigente |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | $52.000 | aprobada | 1 |
| 2 | 2 | 1 | $29.980 | aprobada | 1 |
| 3 | 3 | 1 | $35.960 | rechazada | — |
| 4 | 6 | 1 | $23.990 | aprobada | 1 |

El presupuesto 4 (orden 6) fue el usado para verificar en vivo los avisos
`presupuesto.enviado` y `presupuesto.decidido`.

Los presupuestos tienen **ítems de dos tipos**:

- `repuesto`: referencia a un `repuesto_id` del inventario.
- `mano_de_obra`: solo descripción, cantidad y precio unitario.

---

## 5. Evidencias

Todas están en la **orden 1** (3 archivos PNG de 70 bytes usados como prueba):

| Evidencia | Contexto | Visible al cliente | Estado |
| --- | --- | --- | --- |
| `7b5b5227-e676-41be-99c7-7c372fb1436b` | diagnostico | **No** | confirmada |
| `5b70b8e4-8d2f-49b8-bfe5-223a26ab6682` | presupuesto | Sí | confirmada |
| `4f6dcb48-d629-4c8c-8658-1668cd320794` | reparacion | Sí | confirmada |

Contextos válidos: `diagnostico`, `presupuesto`, `reparacion`,
`resultado_final`.

> La evidencia de contexto `diagnostico` es **interna** (`visible_cliente=false`):
> sirve para comprobar que el cliente no la ve en su listado.

Las evidencias se guardan en el bucket **`evidencias`** de MinIO y se descargan
con una URL prefirmada de 300 segundos.

---

## 6. Proveedores, repuestos e inventario

| Proveedor | ID | Contacto | Tipo |
| --- | --- | --- | --- |
| Repuestos Central UCT | 1 | ventas@repuestoscentral.cl | oficial |

| Repuesto | ID | Proveedor | Stock | Umbral efectivo | Bajo umbral |
| --- | --- | --- | --- | --- | --- |
| Filtro de aceite Toyota | 1 | 1 | 2 | 3 | **Sí** |

- **Umbral general:** 3 unidades.
- **Umbral particular:** ninguno (el repuesto usa el general).
- **Comprometido:** 1 unidad reservada por la orden 6 → **disponible = 1**.
- El stock bajo genera el aviso `stock.alerta` a los administradores.

El repuesto 1 se usó para verificar reserva, consumo, liberación y alerta de
stock.

---

## 7. Notificaciones generadas

Al cierre de la verificación había:

| Destinatario | Total | Tipos presentes |
| --- | --- | --- |
| Administradores | 7 | `presupuesto.decidido`, `stock.alerta`, `nueva_atencion.solicitada` |
| Cliente (usuario 1) | 28 | `orden.estado_cambiado`, `presupuesto.enviado`, `nueva_atencion.revisada` |

También existe un dispositivo push de prueba registrado y luego **desactivado**
(`plataforma: android`). Un dispositivo desactivado no recibe push.

---

## 8. Solicitudes de nueva atención

| Solicitud | Orden cancelada | Vehículo | Situación | Orden generada |
| --- | --- | --- | --- | --- |
| 1 | 3 | 3 (`IJKL56`) | aceptada | 7 |

Flujo probado: el cliente solicita → el administrador revisa y acepta → se genera
una orden nueva en estado `1`.

---

## 9. Cómo reiniciar los datos de prueba

No hay un script de "reset" porque las bases contienen datos reales de la
demostración. Si necesitas partir de cero:

1. **Solo usuarios:** volver a ejecutar el seed (idempotente).
2. **Todo el ambiente:** recrear los addons PostgreSQL (borra las 4 bases),
   volver a migrar y volver a ejecutar el seed. Después hay que recrear
   vehículos, órdenes, presupuestos, proveedor, repuesto y evidencias por API.
3. **Solo un flujo:** crear datos nuevos con otro vehículo (por ejemplo
   `UVWX12` ya está usado; registrar uno nuevo) en lugar de borrar los
   existentes.

> **Cuidado:** borrar una base o un addon es irreversible. Confirmar con el
> responsable antes de hacerlo.

---

## 10. Guion mínimo de demostración

1. Login como **cliente** y revisar vehículos y órdenes.
2. Login como **administrador**: crear una orden para un vehículo nuevo.
3. Asignar **mecánico** (la orden pasa a `2`).
4. Login como **mecánico**: crear presupuesto con un repuesto y mano de obra.
5. **Administrador**: enviar el presupuesto (la orden pasa a `3`).
6. **Cliente**: aprobar el presupuesto (la orden pasa a `5`).
7. **Mecánico**: subir evidencia y registrar bitácora.
8. **Mecánico**: pasar la orden a `6` (Listo).
9. **Administrador**: registrar la entrega (la orden pasa a `7`).
10. Revisar la bandeja de **notificaciones** en cada paso.
