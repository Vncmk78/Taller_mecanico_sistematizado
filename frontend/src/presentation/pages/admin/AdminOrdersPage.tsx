import { useEffect } from 'react';
import { ClipboardList } from 'lucide-react';
import { ordenStatusLabel } from '@/domain/entities/Order';
import { OrderCard } from '@/presentation/components/orders/OrderCard';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OrderListToolbar } from '@/presentation/components/orders/OrderListToolbar';
import { OrderPagination } from '@/presentation/components/orders/OrderPagination';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
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

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;
    const emptyTitle = search.trim()
        ? `No se encontraron órdenes para "${search}".`
        : estadoCodigo !== 'all'
          ? `No hay órdenes en el estado "${ordenStatusLabel(estadoCodigo)}".`
          : 'Aún no hay órdenes de trabajo.';

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

            {isServerError && filteredOrders.length > 0 && (
                <Alert
                    tone="error"
                    className="mx-10 mb-6"
                    action={<RetryButton tone="error" onClick={loadOrders} />}
                >
                    {error ?? 'No se pudieron cargar las órdenes.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'loading' ? (
                <OrderListSkeleton className="px-10 pb-10" />
            ) : isServerError && filteredOrders.length === 0 ? (
                <ErrorState
                    className="px-10 pb-10"
                    title="No se pudieron cargar las órdenes"
                    message={error}
                    onRetry={loadOrders}
                />
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
                            <EmptyState
                                icon={ClipboardList}
                                title={emptyTitle}
                                description={
                                    search.trim() || estadoCodigo !== 'all'
                                        ? 'Pruebe con otro término de búsqueda o estado.'
                                        : 'Las órdenes que se creen aparecerán aquí.'
                                }
                            />
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