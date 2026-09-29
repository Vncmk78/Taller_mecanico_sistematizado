import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { OrderDetailPanel } from '@/presentation/components/orders/OrderDetailPanel';
import { OrderStatusAndHistory } from '@/presentation/components/orders/OrderStatusAndHistory';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { useOrderDetail } from '@/presentation/hooks/useOrderDetail';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function AdminOrderDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { order, loading, notFound, refetch } = useOrderDetail(id, (oid) =>
        orderService.getOrderById(oid)
    );
    const { isOffline, error } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    if (loading) {
        return <div className="p-10 text-text-muted">Cargando detalle de la orden...</div>;
    }

    if (!order || notFound) {
        return (
            <div className="p-10 text-text-muted">
                Orden no encontrada.{' '}
                <Link to="/admin/ordenes" className="text-primary-red">
                    Volver a la gestión de órdenes
                </Link>
            </div>
        );
    }

    return (
        <div className="animate-fade-in p-10">
            <Link
                to="/admin/ordenes"
                className="inline-flex items-center gap-2 text-text-muted hover:text-white mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a la gestión de órdenes
            </Link>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} className="mb-6" />}

            <OrderDetailPanel
                order={order}
                patente={orderPatente(order, vehicles)}
                vehicleLabel={orderVehicleLabel(order, vehicles)}
            />

            <OrderStatusAndHistory order={order} />
        </div>
    );
}