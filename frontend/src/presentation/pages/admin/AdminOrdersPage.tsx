import { useEffect, useState } from 'react';
import { ClipboardList, ClipboardPlus } from 'lucide-react';
import { ordenStatusLabel } from '@/domain/entities/Order';
import { OrderCard } from '@/presentation/components/orders/OrderCard';
import { RegistrarIngresoPanel } from '@/presentation/components/orders/RegistrarIngresoPanel';
import { Button } from '@/presentation/components/ui/Button';
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
import { isInitialLoad } from '@/infrastructure/stores/asyncCollection';

export function AdminOrdersPage() {
    const { orders, status, error, isOffline, requestId, fetchOrders } = useOrderStore();
    const vehicles = useVehicleStore((s) => s.vehicles);
    const [registrando, setRegistrando] = useState(false);

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
    } = useOrderListFilters(
        orders,
        (o) =>
            [o.id, orderPatente(o, vehicles) ?? '', orderVehicleLabel(o, vehicles), ordenStatusLabel(o.estadoCodigo)].join(
                ' '
            ),
        { syncWithUrl: true }
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
            <div className="flex justify-between items-center px-4 sm:px-6 lg:px-10 pt-10 pb-6 gap-4 flex-wrap">
                <div>
                    <h2 className="text-3xl font-bold mb-2 tracking-tight">Gestión de Órdenes</h2>
                    <p className="text-text-muted text-lg">Administración de órdenes de trabajo del taller</p>
                </div>
                <Button
                    variant={registrando ? 'secondary' : 'accent'}
                    onClick={() => setRegistrando((v) => !v)}
                    aria-expanded={registrando}
                    className="flex items-center gap-2"
                >
                    <ClipboardPlus className="w-5 h-5" aria-hidden />
                    {registrando ? 'Cerrar registro de ingreso' : 'Registrar ingreso'}
                </Button>
            </div>
            {registrando && (
                <div className="px-4 sm:px-6 lg:px-10 pb-6">
                    <RegistrarIngresoPanel />
                </div>
            )}

            <div className="px-4 sm:px-6 lg:px-10 pb-6">
                <OrderListToolbar
                    search={search}
                    onSearchChange={setSearch}
                    estadoCodigo={estadoCodigo}
                    onEstadoChange={setEstadoCodigo}
                />
            </div>

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} requestId={requestId} className="mx-4 sm:mx-6 lg:mx-10 mb-6" />}

            {isServerError && filteredOrders.length > 0 && (
                <Alert
                    tone="error"
                    className="mx-4 sm:mx-6 lg:mx-10 mb-6"
                    action={<RetryButton tone="error" onClick={loadOrders} />}
                >
                    {error ?? 'No se pudieron cargar las órdenes.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {isInitialLoad(status, filteredOrders.length > 0) ? (
                <OrderListSkeleton className="px-4 sm:px-6 lg:px-10 pb-10" />
            ) : isServerError && filteredOrders.length === 0 ? (
                <ErrorState
                    className="px-4 sm:px-6 lg:px-10 pb-10"
                    title="No se pudieron cargar las órdenes"
                    message={error}
                    requestId={requestId}
                    onRetry={loadOrders}
                />
            ) : (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 px-4 sm:px-6 lg:px-10 pb-10">
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
                        className="px-4 sm:px-6 lg:px-10 pb-10"
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