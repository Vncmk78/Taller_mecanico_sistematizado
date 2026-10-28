import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ClipboardX, Images } from 'lucide-react';
import { OrderDetailPanel } from '@/presentation/components/orders/OrderDetailPanel';
import { OrderActionsPanel } from '@/presentation/components/orders/OrderActionsPanel';
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
import { EvidenceUploadForm } from '@/presentation/components/evidence/EvidenceUploadForm';
import { EvidenceList } from '@/presentation/components/evidence/EvidenceList';

export function AdminOrderDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { order, loading, notFound, failed, refetch } = useOrderDetail(id, (oid) =>
        orderService.getOrderById(oid)
    );
    const { isOffline, error, requestId } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);
    const [evidenciasAbiertas, setEvidenciasAbiertas] = useState(true);
    const [evidenciasRefresh, setEvidenciasRefresh] = useState(0);

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
                requestId={requestId}
                onRetry={refetch}
                action={
                    <Link to="/admin/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a la gestión de órdenes
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
                    <Link
                        to="/admin/ordenes"
                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                    >
                        Volver a la gestión de órdenes
                    </Link>
                }
            />
        );
    }

    return (
        <div className="animate-fade-in p-10">
            <Link
                to="/admin/ordenes"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a la gestión de órdenes
            </Link>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />}

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

            <section className="card p-6 mt-6" aria-labelledby="admin-order-evidence-title">
                <button
                    type="button"
                    onClick={() => setEvidenciasAbiertas((prev) => !prev)}
                    className="w-full flex items-center justify-between gap-4 text-left"
                    aria-expanded={evidenciasAbiertas}
                    aria-controls="admin-order-evidence-panel"
                >
                    <h3 id="admin-order-evidence-title" className="flex items-center gap-2 text-xl font-semibold">
                        <Images className="h-5 w-5 text-text-muted" aria-hidden />
                        Evidencias
                    </h3>
                    <span className="text-sm text-text-muted">{evidenciasAbiertas ? 'Ocultar' : 'Mostrar'}</span>
                </button>

                {evidenciasAbiertas && (
                    <div id="admin-order-evidence-panel" className="mt-6">
                        <EvidenceUploadForm
                            orderId={order.id}
                            className="mb-6 border-b border-border-custom pb-6"
                            onSuccess={() => setEvidenciasRefresh((n) => n + 1)}
                        />

                        <EvidenceList ordenId={order.id} refreshKey={evidenciasRefresh} />
                    </div>
                )}
            </section>

            <OrderActionsPanel order={order} className="mt-6" />
        </div>
    );
}