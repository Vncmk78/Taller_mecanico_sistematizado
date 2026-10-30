import type { BitacoraEntradaCrear, BitacoraEntry } from '../entities/Bitacora';
import type { Order } from '../entities/Order';
import type { OrderHistoryEntry } from '../entities/OrderHistory';

export interface OrderPort {
    /** Página del historial de órdenes de un vehículo visible para el rol autenticado. */
    getVehicleOrderHistory(
        vehicleId: string,
        page: { limit: number; offset: number }
    ): Promise<{ items: Order[]; total: number; limit: number; offset: number }>;
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
    /** Administrador confirma una solicitud pendiente; MS2 verifica la aprobación en MS3. */
    confirmarCancelacion(ordenId: string): Promise<Order>;
}
