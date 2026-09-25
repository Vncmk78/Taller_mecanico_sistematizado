import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { ordenStatusLabel } from '@/domain/entities/Order';
import type { Order } from '@/domain/entities/Order';
import { OrderCard } from '@/presentation/components/orders/OrderCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function AdminOrdersPage() {
    const [search, setSearch] = useState('');
    const { orders, status, error, isOffline, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return orders;
        const haystack = (o: Order) =>
            [
                o.id,
                orderPatente(o, vehicles) ?? '',
                orderVehicleLabel(o, vehicles),
                ordenStatusLabel(o.estadoCodigo),
            ]
                .join(' ')
                .toLowerCase();
        return orders.filter((o) => haystack(o).includes(term));
    }, [orders, search, vehicles]);

    return (
        <div className="animate-fade-in">
            <div className="flex justify-between items-center px-10 pt-10 pb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Gestión de Órdenes</h2>
                    <p className="text-text-muted text-lg">Administración de órdenes de trabajo del taller</p>
                </div>
                <div className="relative w-full sm:w-[320px]">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Buscar por n° de orden, patente o estado..."
                        className="w-full py-3 pl-11 pr-4 bg-black/40 border border-border-custom rounded-lg text-white text-sm outline-none focus:border-primary-red"
                    />
                </div>
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} className="mx-10 mb-6" />}

            {status === 'loading' ? (
                <OrderListSkeleton className="px-10 pb-10" />
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 px-10 pb-10">
                    {filtered.map((order) => (
                        <OrderCard
                            key={order.id}
                            order={order}
                            detailPath={`/admin/ordenes/${order.id}`}
                            patente={orderPatente(order, vehicles)}
                            vehicleLabel={orderVehicleLabel(order, vehicles)}
                            mechanicName={order.mecanicoNombre}
                        />
                    ))}
                    {filtered.length === 0 && (
                        <p className="text-text-muted col-span-full text-center py-10">
                            {search ? `No se encontraron órdenes para "${search}".` : 'Aún no hay órdenes de trabajo.'}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}