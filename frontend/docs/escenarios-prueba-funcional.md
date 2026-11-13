# Escenarios de prueba funcional — Taller Mecánico Sistematizado

Documento de referencia para pruebas manuales y trazabilidad con la suite automatizada (Vitest en `frontend/`, pytest en `backend/`).

## Convenciones

- **Roles:** `cliente`, `mecanico`, `administrador`.
- **Precondiciones:** usuario autenticado con el rol indicado; datos semilla cargados.
- **Resultado esperado:** comportamiento observable en la UI o respuesta HTTP.
- **Automatizado:** `Sí` si existe prueba automatizada asociada; `No` si es solo manual.

## Autenticación y acceso

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| AUTH-01 | público | Login válido por rol | Ingresar credenciales válidas | Redirige al portal del rol | Sí (`LoginPage.test.tsx`, `AuthService.test.ts`) |
| AUTH-02 | público | Credenciales inválidas | Ingresar contraseña incorrecta | Mensaje de error, sin enumerar usuarios | Sí (`AuthService.test.ts`) |
| AUTH-03 | público | Token expirado | Usar token expirado | 401 y redirección a login | Parcial (smoke) |
| AUTH-04 | cliente | Acceso denegado a ruta admin | Abrir `/admin` | Redirige a `/acceso-denegado` | Sí (`ProtectedRoute.test.tsx`) |

## Vehículos

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| VEH-01 | admin/mecánico | Listar vehículos | Abrir `/admin/vehiculos` o `/mechanic/vehiculos` | Lista con búsqueda y estados | Sí (`AdminVehiclesPage`, `MechanicVehiclesPage`) |
| VEH-02 | cliente | Alta de vehículo | Completar formulario | Vehículo creado y visible | Sí (`ClientVehicleFormPage.test.tsx`) |
| VEH-03 | admin/mecánico | Detalle de vehículo | Abrir detalle | Ficha técnica e historial | Sí (`AdminVehicleDetailPage`, `MechanicVehicleDetailPage`) |

## Órdenes

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| ORD-01 | admin | Listar y filtrar órdenes | Abrir `/admin/ordenes`, filtrar por estado | Lista paginada y filtrada | Sí (`AdminOrdersPage.test.tsx`) |
| ORD-02 | mecánico | Mis órdenes | Abrir `/mechanic/ordenes` | Solo órdenes asignadas | Sí (`MechanicOrdersPage.test.tsx`) |
| ORD-03 | cliente | Mis órdenes | Abrir `/client/ordenes` | Solo órdenes propias | Sí (`ClientOrdersPage.test.tsx`) |
| ORD-04 | admin/mecánico | Cambiar estado | Avanzar estado con observación | Estado actualizado e historial | Sí (`MechanicStatusPage.test.tsx`) |
| ORD-05 | admin | Asignar mecánico | Asignar responsable | Orden asignada | Sí (`OrderActionsPanel.test.tsx`) |
| ORD-06 | cliente/admin | Cancelar orden | Solicitar/confirmar cancelación | Estado cancelado o pendiente | Sí (`OrderActionsPanel.test.tsx`) |

## Presupuestos

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| PRE-01 | mecánico/admin | Crear presupuesto | Abrir orden y crear versión 1 con ítems | Presupuesto en borrador | Sí (`MechanicBudgetPage.test.tsx`) |
| PRE-02 | mecánico/admin | Agregar mano de obra y repuestos | Completar ítems | Ítems visibles con procedencia | Sí (`MechanicBudgetPage`, `BudgetItemRow`) |
| PRE-03 | administrador | Enviar presupuesto | Enviar versión al cliente | Estado enviada y orden en espera de aprobación | Sí (`PresupuestoService.test.ts`) |
| PRE-04 | cliente | Aprobar presupuesto | Revisar y aprobar | Estado aprobado y orden en reparación/esperando repuestos | Sí (`ClientBudgetDetailPage.test.tsx`) |
| PRE-05 | cliente | Rechazar presupuesto | Rechazar con motivo | Estado rechazado y motivo registrado | Sí (`ClientBudgetDetailPage.test.tsx`) |
| PRE-06 | cliente | Rechazar antes de primera aprobación | Confirmar cancelación | Orden cancelada | Sí (`ClientBudgetDetailPage.test.tsx`) |
| PRE-07 | mecánico/admin | Nueva versión | Crear versión modificada | Historial conservado | Sí (`PresupuestoService.test.ts`) |

## Inventario y stock

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| INV-01 | admin/mecánico | Listar repuestos | Abrir `/admin/inventario` o `/mechanic/inventario` | Lista con estado de stock; el mecánico ve *Ver stock* y no ve acciones de escritura | Sí (`AdminInventoryPage.test.tsx`) |
| INV-02 | admin | Filtrar por texto y estado | Buscar y filtrar | Resultados acotados | Sí (`AdminInventoryPage.test.tsx`) |
| INV-03 | admin/mecánico | Alertas de stock | Abrir alertas | Repuestos bajo umbral | Sí (`AdminInventoryAlertsPage.test.tsx`) |
| INV-04 | admin/mecánico | Movimientos de stock | Abrir movimientos | Historial filtrable; el mecánico registra solo movimientos de sus órdenes | Sí (`AdminInventoryMovementsPage.test.tsx`) |
| INV-05 | admin/mecánico | Stock por repuesto | Abrir detalle de stock | Físico, comprometido, disponible | Sí (`AdminStockDetailPage.test.tsx`) |
| INV-06 | admin/mecánico | Umbral general | Consultar valor e historial; el administrador puede cambiarlo | El mecánico no ve el formulario de cambio | Sí (`AdminThresholdPage.test.tsx`) |
| INV-07 | admin | CRUD de repuestos | Crear/editar/eliminar | Catálogo actualizado | Parcial (servicio) |
| INV-08 | admin | CRUD de proveedores | Crear/editar/eliminar | Catálogo actualizado | Parcial (servicio) |
| INV-09 | mecánico | Inventario de consulta | Recorrer `/mechanic/inventario*` | Catálogo, alertas, stock, umbral y distribuidores en solo lectura | Sí (`AppRoutes.test.tsx`, pruebas de modo mecánico) |
| INV-10 | mecánico | Movimiento de orden asignada | Registrar `compromiso`, `consumo` o `liberación` con orden | Movimiento registrado; sin orden se rechaza en la UI | Sí (`AdminInventoryMovementsPage.test.tsx`) |

## Disponibilidad de stock en órdenes

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| STK-01 | mecánico/admin | Consultar disponibilidad | Abrir detalle de orden | Muestra disponible/faltantes | Sí (`MechanicOrderDetailPage`, `AdminOrderDetailPage`) |
| STK-02 | mecánico/admin | Reservar stock | Pulsar "Reservar stock" | Reserva creada o faltantes | Sí (servicio + vista) |
| STK-03 | mecánico/admin | Liberar reserva | Pulsar "Liberar reserva" | Reserva liberada | Sí (servicio + vista) |
| STK-04 | mecánico/admin | Stock insuficiente | Intentar reservar sin stock | Mensaje con faltantes y requestId | Sí (`InventarioService.test.ts`) |

## Evidencias

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| EVI-01 | mecánico/admin | Subir evidencia | Subir archivo en orden | Evidencia visible | Sí (`EvidenceUploadForm.test.tsx`) |
| EVI-02 | cliente | Consultar evidencias | Abrir evidencias de orden | Galería visible | Sí (`ClientOrderEvidencePage.test.tsx`) |

## Estados offline y errores

| ID | Rol | Objetivo | Pasos | Resultado esperado | Automatizado |
|---|---|---|---|---|---|
| OFF-01 | cualquiera | Sin conexión | Simular red caída | `OfflineBanner` con datos parciales | Sí (`AdminVehiclesPage.test.tsx`) |
| OFF-02 | cualquiera | Error de servidor | Simular 500 | `ErrorState` con requestId | Sí (vistas con offline) |
| OFF-03 | cualquiera | Reintento | Pulsar "Reintentar" | Recarga exitosa | Sí (vistas con offline) |

## Resumen de cobertura

- **Frontend (Vitest):** componentes, vistas, servicios y estados.
- **Backend (pytest):** autenticación, autorización, órdenes, presupuestos, inventario, gateway.
- **Smoke HTTP:** cadena Gateway ↔ MS1/MS2.

Mantener este documento actualizado cuando se agreguen o modifiquen flujos.