import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { OrderCard } from '@/presentation/components/orders/OrderCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { orderService } from '@/infrastructure/api/OrderService';
import { CURRENT_CLIENT_ID } from '@/infrastructure/mocks/vehicles.mock';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function ClientOrdersPage() {
    const [search, setSearch] = useState('');
    const user = useAuthStore((s) => s.user);
    const { orders, status, error, isOffline, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const clientId = user?.id ?? CURRENT_CLIENT_ID;
    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const myOrders = useMemo(() => {
        if (!isOffline) return orders;
        const myVehicleIds = new Set(
            vehicles.filter((v) => v.clientId === clientId).map((v) => v.id)
        );
        return orders.filter((o) => myVehicleIds.has(o.vehicleId));
    }, [orders, isOffline, vehicles, clientId]);

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return myOrders;
        const haystack = (o: Order) =>
            [o.id, orderPatente(o, vehicles) ?? '', orderVehicleLabel(o, vehicles)]
                .join(' ')
                .toLowerCase();
        return myOrders.filter((o) => haystack(o).includes(term));
    }, [myOrders, search, vehicles]);

    return (
        <div className="animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-1">Mis Órdenes</h2>
                    <p className="text-text-muted">Consulte el estado de los servicios de sus vehículos</p>
                </div>
            </div>

            <div className="relative w-full sm:w-[320px] mb-6">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Buscar por n° de orden, patente o estado..."
                    className="w-full py-2.5 pl-11 pr-4 bg-black/40 border border-border-custom rounded-lg text-white text-sm outline-none focus:border-primary-red"
                />
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} className="mb-6" />}

            {status === 'loading' ? (
                <OrderListSkeleton count={2} />
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    {filtered.map((order) => (
                        <OrderCard
                            key={order.id}
                            order={order}
                            detailPath={`/client/ordenes/${order.id}`}
                            patente={orderPatente(order, vehicles)}
                            vehicleLabel={orderVehicleLabel(order, vehicles)}
                            mechanicName={order.mecanicoNombre}
                        />
                    ))}
                    {filtered.length === 0 && (
                        <p className="text-text-muted col-span-full text-center py-10">
                            {search
                                ? `No se encontraron órdenes para "${search}".`
                                : 'Aún no tiene órdenes de trabajo registradas.'}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}