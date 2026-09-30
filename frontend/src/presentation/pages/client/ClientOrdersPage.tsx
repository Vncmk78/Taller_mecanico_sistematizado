import { useEffect } from 'react';
import { ordenStatusLabel } from '@/domain/entities/Order';
import { OrderCard } from '@/presentation/components/orders/OrderCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OrderListToolbar } from '@/presentation/components/orders/OrderListToolbar';
import { OrderPagination } from '@/presentation/components/orders/OrderPagination';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useOrderListFilters } from '@/presentation/hooks/useOrderListFilters';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function ClientOrdersPage() {
    const { orders, status, error, isOffline, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Online la Gateway ya devuelve solo las órdenes del cliente autenticado; la
    // caché conserva esa misma respuesta, así que offline no hace falta volver
    // a filtrar por identidad.
    const myOrders = orders;

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
        [o.id, orderPatente(o, vehicles) ?? '', orderVehicleLabel(o, vehicles), ordenStatusLabel(o.estadoCodigo)].join(
            ' '
        )
    );

    return (
        <div className="animate-fade-in">
            <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-1">Mis Órdenes</h2>
                    <p className="text-text-muted">Consulte el estado de los servicios de sus vehículos</p>
                </div>
            </div>

            <OrderListToolbar
                className="mb-6"
                search={search}
                onSearchChange={setSearch}
                estadoCodigo={estadoCodigo}
                onEstadoChange={setEstadoCodigo}
            />

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} className="mb-6" />}

            {status === 'loading' ? (
                <OrderListSkeleton count={2} />
            ) : (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        {pagedOrders.map((order) => (
                            <OrderCard
                                key={order.id}
                                order={order}
                                detailPath={`/client/ordenes/${order.id}`}
                                patente={orderPatente(order, vehicles)}
                                vehicleLabel={orderVehicleLabel(order, vehicles)}
                                mechanicName={order.mecanicoNombre}
                            />
                        ))}
                        {filteredOrders.length === 0 && (
                            <p className="text-text-muted col-span-full text-center py-10">
                                {search
                                    ? `No se encontraron órdenes para "${search}".`
                                    : estadoCodigo !== 'all'
                                      ? `No hay órdenes en el estado "${ordenStatusLabel(estadoCodigo)}".`
                                      : 'Aún no tiene órdenes de trabajo registradas.'}
                            </p>
                        )}
                    </div>

                    <OrderPagination
                        className="pt-2 pb-6"
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