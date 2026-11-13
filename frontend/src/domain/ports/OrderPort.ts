import type { BitacoraEntradaCrear, BitacoraEntry } from '../entities/Bitacora';
import type { Order } from '../entities/Order';
import type { OrderHistoryEntry } from '../entities/OrderHistory';
import type { SolicitudCancelacion } from '../entities/SolicitudCancelacion';

export interface OrderPort {
    /** Página del historial de órdenes de un vehículo visible para el rol autenticado. */
    getVehicleOrderHistory(
        vehicleId: string,
        page: { limit: number; offset: number }
    ): Promise<{ items: Order[]; total: number; limit: number; offset: number }>;
    /** Lista de órdenes visibles para el rol autenticado (el servidor filtra por rol). */
    getOrders(): Promise<Order[]>;
    /**
     * Registra el ingreso físico y crea la orden en Recibido, sin mecánico
     * (POST /ordenes, solo Administrador). MS2 valida el cupo diario y reutiliza
     * el ingreso abierto del vehículo si existe, sin contarlo dos veces.
     */
    crearOrden(vehiculoId: string): Promise<Order>;
    /** Detalle visible; soloPropietario exige propiedad incluso en cuentas multirrol. */
    getOrderById(id: string, options?: { soloPropietario?: boolean }): Promise<Order>;
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
    /**
     * Registra la devolución física del vehículo de una orden Cancelada
     * (POST /ordenes/{id}/devolucion, solo Administrador). La orden sigue
     * Cancelada; MS2 decide fecha y responsable, cierra el ingreso y, si se
     * repite, devuelve los datos originales.
     */
    registrarDevolucion(ordenId: string): Promise<Order>;
    /**
     * Solicitudes de cancelación pendientes de revisión
     * (GET /ordenes/cancelaciones/pendientes, solo Administrador).
     */
    getCancelacionesPendientes(): Promise<SolicitudCancelacion[]>;
    /** Cancelación iniciada por el cliente propietario (POST /ordenes/{id}/cancelacion). */
    cancelarComoCliente(ordenId: string, motivo: string): Promise<Order>;
    /** Administrador confirma una solicitud pendiente; MS2 verifica la aprobación en MS3. */
    confirmarCancelacion(ordenId: string): Promise<Order>;
}
