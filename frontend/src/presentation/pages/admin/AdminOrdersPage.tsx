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

export function AdminOrdersPage() {
    const { orders, status, error, isOffline, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

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
    } = useOrderListFilters(orders, (o) =>
        [o.id, orderPatente(o, vehicles) ?? '', orderVehicleLabel(o, vehicles), ordenStatusLabel(o.estadoCodigo)].join(
            ' '
        )
    );

    return (
        <div className="animate-fade-in">
            <div className="flex justify-between items-center px-10 pt-10 pb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Gestión de Órdenes</h2>
                    <p className="text-text-muted text-lg">Administración de órdenes de trabajo del taller</p>
                </div>
            </div>

            <div className="px-10 pb-6">
                <OrderListToolbar
                    search={search}
                    onSearchChange={setSearch}
                    estadoCodigo={estadoCodigo}
                    onEstadoChange={setEstadoCodigo}
                />
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} className="mx-10 mb-6" />}

            {status === 'loading' ? (
                <OrderListSkeleton className="px-10 pb-10" />
            ) : (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 px-10 pb-10">
                        {pagedOrders.map((order) => (
                            <OrderCard
                                key={order.id}
                                order={order}
                                detailPath={`/admin/ordenes/${order.id}`}
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
                                      : 'Aún no hay órdenes de trabajo.'}
                            </p>
                        )}
                    </div>

                    <OrderPagination
                        className="px-10 pb-10"
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