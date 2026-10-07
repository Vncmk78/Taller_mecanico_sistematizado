import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, RefreshCw, SearchX } from 'lucide-react';
import { OrderDetailPanel } from '@/presentation/components/orders/OrderDetailPanel';
import { OrderStatusAndHistory } from '@/presentation/components/orders/OrderStatusAndHistory';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { Button } from '@/presentation/components/ui/Button';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { useOrderDetail } from '@/presentation/hooks/useOrderDetail';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function ClientOrderDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { order, loading, notFound, refetch } = useOrderDetail(id, (oid) =>
        orderService.getOrderById(oid)
    );
    const { isOffline, error } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    if (loading) {
        return <LoadingState message="Cargando detalle de la orden..." className="p-5 sm:p-8 lg:p-10" />;
    }

    // El fetch falló (red o servidor) y no hay una orden en caché: es un error de
    // carga, no un "no encontrado" confirmado por el backend (404).
    if (error && !order) {
        return (
            <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
                <div className="card p-8 sm:p-14 text-center">
                    <span className="flex items-center justify-center w-14 h-14 rounded-full bg-status-red/10 text-status-red mx-auto mb-4">
                        <AlertTriangle className="w-6 h-6" aria-hidden />
                    </span>
                    <p className="text-text-main text-lg font-semibold mb-2">
                        No se pudieron cargar los datos del servicio
                    </p>
                    <p className="text-text-muted text-sm max-w-md mx-auto mb-6">{error}</p>
                    <Button variant="primary" onClick={refetch} className="inline-flex items-center gap-2">
                        <RefreshCw className="w-4 h-4" aria-hidden /> Reintentar
                    </Button>
                </div>
            </div>
        );
    }

    if (!order || notFound) {
        return (
            <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
                <div className="card p-8 sm:p-14 text-center">
                    <span className="flex items-center justify-center w-14 h-14 rounded-full bg-bg-secondary text-text-muted mx-auto mb-4">
                        <SearchX className="w-6 h-6" aria-hidden />
                    </span>
                    <p className="text-text-main text-lg font-semibold mb-2">Orden no encontrada.</p>
                    <p className="text-text-muted text-sm max-w-md mx-auto mb-6">
                        El servicio no existe o no pertenece a su cuenta. Verifique que la dirección
                        sea correcta o consulte su listado de servicios.
                    </p>
                    <Link
                        to="/client/ordenes"
                        className="inline-flex items-center gap-2 bg-primary-blue text-white px-6 py-3 rounded-lg font-bold no-underline hover:bg-primary-blue-hover transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" aria-hidden /> Volver a mis órdenes
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
            <Link
                to="/client/ordenes"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a mis órdenes
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