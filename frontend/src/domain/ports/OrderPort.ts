import type { BitacoraEntradaCrear, BitacoraEntry } from '../entities/Bitacora';
import type { Order } from '../entities/Order';
import type { OrderHistoryEntry } from '../entities/OrderHistory';

export interface OrderPort {
    /** Lista de órdenes visibles para el rol autenticado (el servidor filtra por rol). */
    getOrders(): Promise<Order[]>;
    /** Detalle de una orden por id (404 si no está en el alcance del rol). */
    getOrderById(id: string): Promise<Order>;
    /** Historial de cambios de estado de una orden (el servidor filtra por rol). */
    getOrderHistory(ordenId: string): Promise<OrderHistoryEntry[]>;
    /** Bitácora de trabajo del mecánico de una orden (GET /ordenes/{id}/bitacora). */
    getOrderBitacora(ordenId: string): Promise<BitacoraEntry[]>;
    /** Registra una entrada de bitácora (POST /ordenes/{id}/bitacora). */
    registrarBitacora(ordenId: string, entrada: BitacoraEntradaCrear): Promise<BitacoraEntry>;
    /** Cambia el estado de una orden (PATCH /ordenes/{id}/estado). */
    cambiarEstado(
        ordenId: string,
        estadoDestino: number,
        observacion?: string
    ): Promise<Order>;
    /** Asigna o reasigna el mecánico responsable (PUT /ordenes/{id}/mecanico). */
    asignarMecanico(
        ordenId: string,
        mecanicoId: string,
        observacion?: string
    ): Promise<Order>;
    /** Registra la entrega física de la orden (POST /ordenes/{id}/entrega). */
    registrarEntrega(ordenId: string, observacion?: string): Promise<Order>;
    /** Cancelación iniciada por el cliente propietario (POST /ordenes/{id}/cancelacion). */
    cancelarComoCliente(ordenId: string, motivo: string): Promise<Order>;
}