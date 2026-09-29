import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';

// Historial de estados de las órdenes demo. Cada orden termina en su estado
// actual y sus transiciones son siempre válidas (estado_nuevo <> estado_anterior
// y coherentes con el catálogo fijo de 8 estados). TODO: reemplazar por
// orderService.getOrderHistory (MS2) cuando el endpoint esté disponible.
export const mockOrderHistory: OrderHistoryEntry[] = [
    // Orden 101 → En reparación (5)
    { id: 'h-101-1', ordenId: '101', estadoAnteriorCodigo: null, estadoNuevoCodigo: 1, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-01T10:15:00', observacion: 'Ingreso registrado por el administrador' },
    { id: 'h-101-2', ordenId: '101', estadoAnteriorCodigo: 1, estadoNuevoCodigo: 2, actorUsuarioId: 7, origen: 'usuario', fecha: '2026-09-01T11:00:00', observacion: 'Asignada a Martín Herrera', usuarioNombre: 'Administrador del taller' },
    { id: 'h-101-3', ordenId: '101', estadoAnteriorCodigo: 2, estadoNuevoCodigo: 3, actorUsuarioId: 1, origen: 'usuario', fecha: '2026-09-02T09:20:00', observacion: 'Presupuesto v1 enviado al cliente', usuarioNombre: 'Martín Herrera' },
    { id: 'h-101-4', ordenId: '101', estadoAnteriorCodigo: 3, estadoNuevoCodigo: 5, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-02T12:00:00', observacion: 'Presupuesto aprobado con repuestos disponibles' },

    // Orden 102 → Esperando aprobación de presupuesto (3)
    { id: 'h-102-1', ordenId: '102', estadoAnteriorCodigo: null, estadoNuevoCodigo: 1, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-03T09:00:00', observacion: 'Ingreso registrado por el administrador' },
    { id: 'h-102-2', ordenId: '102', estadoAnteriorCodigo: 1, estadoNuevoCodigo: 2, actorUsuarioId: 7, origen: 'usuario', fecha: '2026-09-03T10:10:00', observacion: 'Asignada a Martín Herrera', usuarioNombre: 'Administrador del taller' },
    { id: 'h-102-3', ordenId: '102', estadoAnteriorCodigo: 2, estadoNuevoCodigo: 3, actorUsuarioId: 1, origen: 'usuario', fecha: '2026-09-04T12:20:00', observacion: 'Presupuesto v1 enviado al cliente', usuarioNombre: 'Martín Herrera' },

    // Orden 103 → Esperando diagnóstico (2)
    { id: 'h-103-1', ordenId: '103', estadoAnteriorCodigo: null, estadoNuevoCodigo: 1, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-08T15:40:00', observacion: 'Ingreso registrado por el administrador' },
    { id: 'h-103-2', ordenId: '103', estadoAnteriorCodigo: 1, estadoNuevoCodigo: 2, actorUsuarioId: 7, origen: 'usuario', fecha: '2026-09-09T09:10:00', observacion: 'Asignada a Martín Herrera', usuarioNombre: 'Administrador del taller' },

    // Orden 104 → Esperando repuestos (4)
    { id: 'h-104-1', ordenId: '104', estadoAnteriorCodigo: null, estadoNuevoCodigo: 1, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-10T11:00:00', observacion: 'Ingreso registrado por el administrador' },
    { id: 'h-104-2', ordenId: '104', estadoAnteriorCodigo: 1, estadoNuevoCodigo: 2, actorUsuarioId: 7, origen: 'usuario', fecha: '2026-09-10T12:30:00', observacion: 'Asignada a Gustavo Jara', usuarioNombre: 'Administrador del taller' },
    { id: 'h-104-3', ordenId: '104', estadoAnteriorCodigo: 2, estadoNuevoCodigo: 3, actorUsuarioId: 2, origen: 'usuario', fecha: '2026-09-11T10:00:00', observacion: 'Presupuesto v1 enviado al cliente', usuarioNombre: 'Gustavo Jara' },
    { id: 'h-104-4', ordenId: '104', estadoAnteriorCodigo: 3, estadoNuevoCodigo: 4, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-12T17:45:00', observacion: 'Presupuesto aprobado sin stock disponible; se esperan repuestos' },

    // Orden 105 → Recibido (1)
    { id: 'h-105-1', ordenId: '105', estadoAnteriorCodigo: null, estadoNuevoCodigo: 1, actorUsuarioId: null, origen: 'sistema', fecha: '2026-09-15T08:30:00', observacion: 'Ingreso registrado por el administrador' },

    // Orden 106 → Listo (6)
    { id: 'h-106-1', ordenId: '106', estadoAnteriorCodigo: null, estadoNuevoCodigo: 1, actorUsuarioId: null, origen: 'sistema', fecha: '2026-08-20T14:00:00', observacion: 'Ingreso registrado por el administrador' },
    { id: 'h-106-2', ordenId: '106', estadoAnteriorCodigo: 1, estadoNuevoCodigo: 2, actorUsuarioId: 7, origen: 'usuario', fecha: '2026-08-20T15:00:00', observacion: 'Asignada a Martín Herrera', usuarioNombre: 'Administrador del taller' },
    { id: 'h-106-3', ordenId: '106', estadoAnteriorCodigo: 2, estadoNuevoCodigo: 3, actorUsuarioId: 1, origen: 'usuario', fecha: '2026-08-21T09:30:00', observacion: 'Presupuesto v1 enviado al cliente', usuarioNombre: 'Martín Herrera' },
    { id: 'h-106-4', ordenId: '106', estadoAnteriorCodigo: 3, estadoNuevoCodigo: 5, actorUsuarioId: null, origen: 'sistema', fecha: '2026-08-21T14:00:00', observacion: 'Presupuesto aprobado con repuestos disponibles' },
    { id: 'h-106-5', ordenId: '106', estadoAnteriorCodigo: 5, estadoNuevoCodigo: 6, actorUsuarioId: 1, origen: 'usuario', fecha: '2026-08-25T10:00:00', observacion: 'Trabajo autorizado finalizado; vehículo listo', usuarioNombre: 'Martín Herrera' },
];