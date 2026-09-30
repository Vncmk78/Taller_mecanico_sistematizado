import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ClipboardX } from 'lucide-react';
import { OrderDetailPanel } from '@/presentation/components/orders/OrderDetailPanel';
import { OrderStatusAndHistory } from '@/presentation/components/orders/OrderStatusAndHistory';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { useOrderDetail } from '@/presentation/hooks/useOrderDetail';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function ClientOrderDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { order, loading, notFound, failed, refetch } = useOrderDetail(id, (oid) =>
        orderService.getOrderById(oid)
    );
    const { isOffline, error } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    if (loading) {
        return <LoadingState message="Cargando detalle de la orden..." className="p-10" />;
    }

    // El fetch falló y no hay copia local: se muestra un error reintentable en
    // lugar de un "no encontrada" que no es cierto.
    if (failed) {
        return (
            <ErrorState
                className="p-10"
                title="No se pudo cargar el detalle de la orden"
                message={error}
                onRetry={refetch}
                action={
                    <Link to="/client/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a mis órdenes
                    </Link>
                }
            />
        );
    }

    if (!order || notFound) {
        return (
            <EmptyState
                className="p-10"
                icon={ClipboardX}
                title="Orden no encontrada."
                description="Verifique el número de orden o que la orden siga disponible."
                action={
                    <Link to="/client/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a mis órdenes
                    </Link>
                }
            />
        );
    }

    return (
        <div className="animate-fade-in p-10">
            <Link
                to="/client/ordenes"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a mis órdenes
            </Link>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} className="mb-6" />}

            {/* Error del servidor con copia local en caché: se conserva la orden y se avisa. */}
            {!isOffline && error && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
                    {error} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            <OrderDetailPanel
                order={order}
                patente={orderPatente(order, vehicles)}
                vehicleLabel={orderVehicleLabel(order, vehicles)}
            />

            <OrderStatusAndHistory order={order} />
        </div>
    );
}