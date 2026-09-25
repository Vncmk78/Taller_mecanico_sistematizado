import type { Order } from '../entities/Order';
import type { OrderHistoryEntry } from '../entities/OrderHistory';

export interface OrderPort {
    /** Lista de órdenes visibles para el rol autenticado (el servidor filtra por rol). */
    getOrders(): Promise<Order[]>;
    /** Detalle de una orden por id (404 si no está en el alcance del rol). */
    getOrderById(id: string): Promise<Order>;
    /** Historial de cambios de estado de una orden (el servidor filtra por rol). */
    getOrderHistory(ordenId: string): Promise<OrderHistoryEntry[]>;
}