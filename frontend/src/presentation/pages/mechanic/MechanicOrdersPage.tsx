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

export function MechanicOrdersPage() {
    const { orders, status, error, isOffline, requestId, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Online la Gateway ya devuelve solo las órdenes asignadas al mecánico
    // autenticado; la caché conserva esa misma respuesta, así que offline no
    // hace falta volver a filtrar por identidad.
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
        [o.id, orderPatente(o, vehicles) ?? '', orderVehicleLabel(o, vehicles)].join(' ')
    );

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;
    const emptyTitle = search.trim()
        ? `No se encontraron órdenes para "${search}".`
        : estadoCodigo !== 'all'
          ? `No tienes órdenes en el estado "${ordenStatusLabel(estadoCodigo)}".`
          : 'No tiene órdenes asignadas por el momento.';

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

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} requestId={requestId} className="mb-6" />}

            {isServerError && filteredOrders.length > 0 && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadOrders} />}>
                    {error ?? 'No se pudieron cargar sus órdenes.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'loading' ? (
                <OrderListSkeleton count={3} />
            ) : isServerError && filteredOrders.length === 0 ? (
                <ErrorState
                    title="No se pudieron cargar sus órdenes"
                    message={error}
                    requestId={requestId}
                    onRetry={loadOrders}
                />
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
                                // MS2 no expone el nombre del mecánico, solo su id real.
                                mechanicName={order.mecanicoNombre ?? order.mecanicoActualId ?? undefined}
                            />
                        ))}
                        {filteredOrders.length === 0 && (
                            <EmptyState
                                icon={ClipboardList}
                                title={emptyTitle}
                                description={
                                    search.trim() || estadoCodigo !== 'all'
                                        ? 'Pruebe con otro término de búsqueda o estado.'
                                        : 'Las órdenes que se le asignen aparecerán aquí.'
                                }
                            />
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