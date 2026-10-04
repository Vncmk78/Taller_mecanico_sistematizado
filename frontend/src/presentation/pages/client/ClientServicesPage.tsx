import { useEffect, useMemo, type ReactElement } from 'react';
import { ClipboardList } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { ServiceCard } from '@/presentation/components/orders/ServiceCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { orderService } from '@/infrastructure/api/OrderService';
import { CURRENT_CLIENT_ID } from '@/infrastructure/mocks/vehicles.mock';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
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
    const user = useAuthStore((s) => s.user);
    const { orders, status, error, isOffline, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const clientId = user?.id ?? CURRENT_CLIENT_ID;
    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const myServices = useMemo(() => {
        if (!isOffline) return orders;
        const myVehicleIds = new Set(
            vehicles.filter((v) => v.clientId === clientId).map((v) => v.id)
        );
        return orders.filter((o) => myVehicleIds.has(o.vehicleId));
    }, [orders, isOffline, vehicles, clientId]);

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
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
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

    return (
        <div className="p-10 animate-fade-in">
            <div className="mb-6">
                <h2 className="text-3xl font-bold mb-1">Estado del Servicio</h2>
                <p className="text-text-muted">Seguimiento en tiempo real del estado de sus servicios en el taller</p>
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} className="mb-6" />}

            {status === 'loading' ? (
                <OrderListSkeleton count={2} />
            ) : (
                <>
                    {renderGroup('Requieren su atención', groups.attention, true)}
                    {renderGroup('En proceso', groups.inProgress)}
                    {renderGroup('Finalizados', groups.finished)}

                    {groups.total === 0 && (
                        <div className="card p-14 text-center">
                            <ClipboardList className="w-12 h-12 text-text-muted mx-auto mb-4" aria-hidden />
                            <p className="text-text-muted text-lg mb-2">Aún no tiene servicios en el taller</p>
                            <p className="text-text-muted text-sm">
                                Registre un vehículo y agende una mantención para comenzar a ver el estado de sus servicios.
                            </p>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}