import { useEffect, useMemo } from 'react';
import { ordenStatusLabel } from '@/domain/entities/Order';
import { OrderCard } from '@/presentation/components/orders/OrderCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OrderListToolbar } from '@/presentation/components/orders/OrderListToolbar';
import { OrderPagination } from '@/presentation/components/orders/OrderPagination';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useOrderListFilters } from '@/presentation/hooks/useOrderListFilters';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { orderService } from '@/infrastructure/api/OrderService';
import { CURRENT_MECHANIC_ID, mockMechanics } from '@/infrastructure/mocks/orders.mock';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function MechanicOrdersPage() {
    const { orders, status, error, isOffline, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const myOrders = useMemo(() => {
        // Cuando hay API, el servidor ya filtra las órdenes del mecánico; el
        // filtro por CURRENT_MECHANIC_ID es solo para los datos de demo.
        if (!isOffline) return orders;
        return orders.filter((o) => o.mecanicoActualId === CURRENT_MECHANIC_ID);
    }, [orders, isOffline]);

    const {
        search,
        setSearch,
        estadoCodigo,
        setEstadoCodigo,
        page,
        setPage,
        pageSize,
        setPageSize,
        filteredOrders,
        pagedOrders,
        total,
        pageCount,
        rangeStart,
        rangeEnd,
    } = useOrderListFilters(myOrders, (o) =>
        [o.id, orderPatente(o, vehicles) ?? '', orderVehicleLabel(o, vehicles)].join(' ')
    );

    return (
        <div className="animate-fade-in p-10">
            <h2 className="text-3xl font-bold mb-2">Mis Órdenes</h2>
            <p className="text-text-muted mb-6">Órdenes de trabajo asignadas a tu cuenta</p>

            <OrderListToolbar
                className="mb-6"
                search={search}
                onSearchChange={setSearch}
                estadoCodigo={estadoCodigo}
                onEstadoChange={setEstadoCodigo}
                searchPlaceholder="Buscar por n° de orden o patente..."
            />

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} className="mb-6" />}

            {status === 'loading' ? (
                <OrderListSkeleton count={3} />
            ) : (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                        {pagedOrders.map((order) => (
                            <OrderCard
                                key={order.id}
                                order={order}
                                detailPath={`/mechanic/ordenes/${order.id}`}
                                patente={orderPatente(order, vehicles)}
                                vehicleLabel={orderVehicleLabel(order, vehicles)}
                                mechanicName={order.mecanicoNombre ?? mockMechanics[String(order.mecanicoActualId)]}
                            />
                        ))}
                        {filteredOrders.length === 0 && (
                            <p className="text-text-muted col-span-full text-center py-10">
                                {search
                                    ? `No se encontraron órdenes para "${search}".`
                                    : estadoCodigo !== 'all'
                                      ? `No tienes órdenes en el estado "${ordenStatusLabel(estadoCodigo)}".`
                                      : 'No tiene órdenes asignadas por el momento.'}
                            </p>
                        )}
                    </div>

                    <OrderPagination
                        className="pt-2 pb-4"
                        page={page}
                        pageCount={pageCount}
                        onPageChange={setPage}
                        pageSize={pageSize}
                        onPageSizeChange={setPageSize}
                        rangeStart={rangeStart}
                        rangeEnd={rangeEnd}
                        total={total}
                    />
                </>
            )}
        </div>
    );
}