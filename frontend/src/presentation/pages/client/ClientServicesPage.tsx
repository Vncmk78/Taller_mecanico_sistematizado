import { useEffect, useMemo, type ReactElement } from 'react';
import { ClipboardList } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { ServiceCard } from '@/presentation/components/orders/ServiceCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

// Estados que requieren atención del cliente (p. ej. aprobar el presupuesto).
const ATTENTION_STATES = new Set([3]);
// Estados terminales del ciclo (vehículo entregado o cancelado).
const FINAL_STATES = new Set([7, 8]);

function sortByUpdateDesc(a: Order, b: Order): number {
    return a.actualizadoEn < b.actualizadoEn ? 1 : -1;
}

export function ClientServicesPage() {
    const { orders, status, error, isOffline, requestId, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Online la Gateway ya devuelve solo las órdenes del cliente autenticado; la
    // caché conserva esa misma respuesta, así que offline no hace falta volver a
    // filtrar por identidad.
    const myServices = orders;

    const groups = useMemo(() => {
        const sorted = [...myServices].sort(sortByUpdateDesc);
        return {
            attention: sorted.filter((o) => ATTENTION_STATES.has(o.estadoCodigo)),
            inProgress: sorted.filter((o) => !ATTENTION_STATES.has(o.estadoCodigo) && !FINAL_STATES.has(o.estadoCodigo)),
            finished: sorted.filter((o) => FINAL_STATES.has(o.estadoCodigo)),
            total: sorted.length,
        };
    }, [myServices]);

    const renderGroup = (
        title: string,
        items: Order[],
        attention = false
    ): ReactElement | null =>
        items.length === 0 ? null : (
            <section aria-label={title} className="mb-8">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <ClipboardList className="w-5 h-5 text-text-muted" aria-hidden />
                    {title}
                    <span className="text-sm font-normal text-text-muted">({items.length})</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    {items.map((order) => (
                        <ServiceCard
                            key={order.id}
                            order={order}
                            detailPath={`/client/ordenes/${order.id}`}
                            vehiclePath={`/client/vehiculos/${order.vehicleId}`}
                            patente={orderPatente(order, vehicles)}
                            vehicleLabel={orderVehicleLabel(order, vehicles)}
                            requiresAttention={attention}
                            attentionLabel="Requiere su atención: presupuesto por aprobar"
                        />
                    ))}
                </div>
            </section>
        );

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="p-5 sm:p-8 lg:p-10 animate-fade-in">
            <div className="mb-6">
                <h2 className="text-3xl font-bold mb-1">Estado del Servicio</h2>
                <p className="text-text-muted">Seguimiento en tiempo real del estado de sus servicios en el taller</p>
            </div>

            {isOffline && (
                <OfflineBanner message={error} onRetry={loadOrders} requestId={requestId} className="mb-6" />
            )}

            {isServerError && groups.total > 0 && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadOrders} />}>
                    {error ?? 'No se pudieron cargar sus servicios.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'loading' ? (
                <OrderListSkeleton count={2} />
) : isServerError && groups.total === 0 ? (
                <ErrorState
                    title="No se pudieron cargar sus servicios"
                    message={error}
                    requestId={requestId}
                    onRetry={loadOrders}
                />
            ) : (
                <>
                    {renderGroup('Requieren su atención', groups.attention, true)}
                    {renderGroup('En proceso', groups.inProgress)}
                    {renderGroup('Finalizados', groups.finished)}

                    {groups.total === 0 && (
<EmptyState
                            icon={ClipboardList}
                            title="Aún no tiene servicios en el taller"
                            description="Registre un vehículo y agende una mantención para comenzar a ver el estado de sus servicios."
                        />
                    )}
                </>
            )}
        </div>
    );
}