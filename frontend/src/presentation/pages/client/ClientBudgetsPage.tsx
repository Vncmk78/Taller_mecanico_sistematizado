import { FileText } from 'lucide-react';
import { BudgetCard } from '@/presentation/components/budgets/BudgetCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { useClientBudgets } from '@/presentation/hooks/useClientBudgets';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function ClientBudgetsPage() {
    const { items, loading, error, isOffline, requestId, failed, refetch } = useClientBudgets();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const isServerError = !isOffline && Boolean(error);

    return (
        <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
            <div className="mb-6">
                <h2 className="text-3xl font-bold mb-1">Mis Presupuestos</h2>
                <p className="text-text-muted">
                    Revise, apruebe o rechace las cotizaciones de sus órdenes de servicio.
                </p>
            </div>

            {isOffline && (
                <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />
            )}

            {isServerError && items.length > 0 && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
                    {error} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {loading ? (
                <OrderListSkeleton count={2} />
            ) : failed ? (
                <ErrorState
                    title="No se pudieron cargar sus presupuestos"
                    message={error}
                    requestId={requestId}
                    onRetry={refetch}
                />
            ) : items.length === 0 ? (
                <EmptyState
                    icon={FileText}
                    title="Aún no tiene presupuestos"
                    description="Cuando el taller envíe la cotización de un servicio, aparecerá aquí para que la apruebe o rechace."
                />
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                    {items.map(({ order, presupuesto }) => (
                        <BudgetCard
                            key={presupuesto.id}
                            order={order}
                            presupuesto={presupuesto}
                            patente={orderPatente(order, vehicles)}
                            vehicleLabel={orderVehicleLabel(order, vehicles)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
