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
    /** Cambia el estado de una orden (PATCH /ordenes/{id}/estado). */
    cambiarEstado(
        ordenId: string,
        estadoDestino: number,
        observacion?: string
    ): Promise<Order>;
}
