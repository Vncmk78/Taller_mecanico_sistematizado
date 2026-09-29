import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderHistory } from '@/presentation/hooks/useOrderHistory';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { OrderHistoryTimeline } from './OrderHistoryTimeline';
import { OrderStateStepper } from './OrderStateStepper';

interface OrderStatusAndHistoryProps {
    order: Order;
}

/**
 * Bloque del detalle de orden que junta el ciclo de estados (stepper) y el
 * historial de cambios (timeline). Usado por los 3 portales sobre el panel de
 * información de la orden.
 */
export function OrderStatusAndHistory({ order }: OrderStatusAndHistoryProps) {
    const { entries, loading, refetch } = useOrderHistory(
        order.id,
        (ordenId) => orderService.getOrderHistory(ordenId)
    );
    const isOffline = useOrderHistoryStore((s) => s.isOffline);
    const error = useOrderHistoryStore((s) => s.error);

    return (
        <div className="mt-6 space-y-6">
            {isOffline && <OfflineBanner message={error} onRetry={refetch} />}
            <OrderStateStepper estadoCodigo={order.estadoCodigo} />
            <OrderHistoryTimeline entries={entries} loading={loading} />
        </div>
    );
}