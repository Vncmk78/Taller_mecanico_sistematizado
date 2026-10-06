import { useEffect, useMemo, useState } from 'react';
import { Check, ClipboardList } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { AVANCES_MECANICO, ESTADOS_ORDEN, ordenStatusLabel } from '@/domain/entities/Order';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { OrderStateStepper } from '@/presentation/components/orders/OrderStateStepper';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OrderListToolbar } from '@/presentation/components/orders/OrderListToolbar';
import { OrderPagination } from '@/presentation/components/orders/OrderPagination';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { ConfirmDialog } from '@/presentation/components/ui/ConfirmDialog';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { useToast } from '@/presentation/components/ui/toastContext';
import { useOrderListFilters } from '@/presentation/hooks/useOrderListFilters';
import { filterOrdersByMechanic, filterVehiclesByOrders } from '@/presentation/utils/mechanicScope';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';

interface OrderAdvanceCardProps {
    order: Order;
    patente?: string;
    vehicleLabel?: string | null;
}

function OrderAdvanceCard({ order, patente, vehicleLabel }: OrderAdvanceCardProps) {
    const [destino, setDestino] = useState('');
    const [observacion, setObservacion] = useState('');
    const [confirming, setConfirming] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const updateOrder = useOrderStore((s) => s.updateOrder);
    const { showToast } = useToast();

    const avances = AVANCES_MECANICO[order.estadoCodigo] ?? [];

    const confirmarAvance = async () => {
        if (!destino) return;
        setSubmitting(true);
        setError('');
        try {
            const actualizada = await orderService.cambiarEstado(
                order.id,
                Number(destino),
                observacion
            );
            updateOrder(actualizada);
            showToast(
                `Orden n° ${order.id} actualizada a ${ordenStatusLabel(actualizada.estadoCodigo)}.`,
                'success'
            );
            setConfirming(false);
            setDestino('');
            setObservacion('');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudo actualizar el estado de la orden.'));
            setConfirming(false);
        } finally {
            setSubmitting(false);
        }
    };

    return (
    <div className="card p-6">
        <div className="flex justify-between items-start gap-3 flex-wrap mb-4">
            <div>
                <h3 className="text-lg font-semibold">Orden n° {order.id}</h3>
                <p className="text-text-muted text-sm">
                    {vehicleLabel}
                    {patente && (
                        <>
                            {' '}
                            · <span className="font-mono">{patente}</span>
                        </>
                    )}
                </p>
            </div>
            <OrderStatusBadge estadoCodigo={order.estadoCodigo} />
        </div>

        <OrderStateStepper estadoCodigo={order.estadoCodigo} />

        <div className="mt-5 pt-5 border-t border-border-custom flex flex-col sm:flex-row gap-3 sm:items-end">
            <label className="flex flex-col gap-1 text-sm flex-1 min-w-40">
                <span className="text-text-muted">Siguiente estado</span>
                <select
                    value={destino}
                    onChange={(e) => setDestino(e.target.value)}
                    aria-label={`Siguiente estado de la orden ${order.id}`}
                    className="w-full py-2.5 px-3 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
                >
                    <option value="">Seleccionar...</option>
                    {avances.map((codigo) => (
                        <option key={codigo} value={codigo}>
                            {ESTADOS_ORDEN[codigo]}
                        </option>
                    ))}
                </select>
            </label>
            <label className="flex flex-col gap-1 text-sm flex-1">
                <span className="text-text-muted">Observación (opcional)</span>
                <input
                    type="text"
                    value={observacion}
                    onChange={(e) => setObservacion(e.target.value)}
                    placeholder="Comentario del avance..."
                    aria-label={`Observación de la orden ${order.id}`}
                    className="w-full py-2.5 px-3 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
                />
            </label>
            <Button
                variant="primary"
                disabled={!destino}
                onClick={() => setConfirming(true)}
                className="shrink-0"
            >
                <span className="flex items-center gap-2">
                    <Check className="w-4 h-4" /> Confirmar avance
                </span>
            </Button>
        </div>

        {error && <Alert tone="error" className="mt-4">{error}</Alert>}

        <ConfirmDialog
            open={confirming}
            tone="primary"
            title="¿Confirmar el avance de estado?"
            description={`La orden n° ${order.id} pasará de ${ordenStatusLabel(order.estadoCodigo)} a ${destino ? ordenStatusLabel(Number(destino)) : ''}.${observacion ? `\nObservación: ${observacion}` : ''}`}
            confirmLabel="Avanzar estado"
            isLoading={submitting}
            onConfirm={confirmarAvance}
            onCancel={() => setConfirming(false)}
        />
    </div>
    );
}

/** Orden que ya no tiene ningún avance del mecánico: la cierra el cliente o el administrador. */
function ClosedOrderCard({ order, patente, vehicleLabel }: OrderAdvanceCardProps) {
    return (
    <div className="card p-6 opacity-80">
        <div className="flex justify-between items-start gap-3 flex-wrap">
            <div>
                <h3 className="text-lg font-semibold">Orden n° {order.id}</h3>
                <p className="text-text-muted text-sm">
                    {vehicleLabel}
                    {patente && (
                        <>
                            {' '}
                            · <span className="font-mono">{patente}</span>
                        </>
                    )}
                </p>
            </div>
            <OrderStatusBadge estadoCodigo={order.estadoCodigo} />
        </div>
        <p className="text-text-muted text-sm mt-4">
            No hay avances disponibles para el mecánico en este estado.
        </p>
    </div>
    );
}

export function MechanicStatusPage() {
    const { orders, status, error, isOffline, requestId, fetchOrders } = useOrderStore();
    const { vehicles: allVehicles, fetchVehicles } = useVehicleStore();
    const mechanicId = useAuthStore((s) => s.user?.id);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // Las tarjetas muestran patente y modelo, que solo se resuelven con los
        // vehículos asignados cargados en la caché compartida.
        fetchVehicles(() => vehicleService.getAssignedVehicles());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const myOrders = filterOrdersByMechanic(orders, mechanicId);
    const vehicles = filterVehiclesByOrders(allVehicles, myOrders);

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
        [
            o.id,
            orderPatente(o, vehicles) ?? '',
            orderVehicleLabel(o, vehicles),
            ordenStatusLabel(o.estadoCodigo),
        ].join(' ')
    );

    // Una orden es accionable cuando AVANCES_MECANICO define algún avance para su
    // estado; el resto depende del cliente o del administrador y se lista aparte
    // para no mostrar un selector sin opciones. La partición se hace sobre la
    // página actual, así la paginación sigue siendo la de useOrderListFilters.
    const actionable = useMemo(
        () => pagedOrders.filter((o) => (AVANCES_MECANICO[o.estadoCodigo]?.length ?? 0) > 0),
        [pagedOrders]
    );
    const closed = useMemo(
        () => pagedOrders.filter((o) => (AVANCES_MECANICO[o.estadoCodigo]?.length ?? 0) === 0),
        [pagedOrders]
    );

    const isServerError = status === 'error' && !isOffline;
    const emptyTitle = search.trim()
        ? `No se encontraron órdenes para "${search}".`
        : estadoCodigo !== 'all'
            ? `No tienes órdenes en el estado "${ordenStatusLabel(estadoCodigo)}".`
            : 'No tiene órdenes asignadas por el momento.';

    return (
    <div className="animate-fade-in p-10">
        <h2 className="text-3xl font-bold mb-2 tracking-tight">Actualizar Estados</h2>
        <p className="text-text-muted text-lg mb-6">Mantén el flujo de las órdenes al día</p>

        <OrderListToolbar
            className="mb-6"
            search={search}
            onSearchChange={setSearch}
            estadoCodigo={estadoCodigo}
            onEstadoChange={setEstadoCodigo}
        />

        {isOffline && <OfflineBanner message={error} onRetry={loadOrders} requestId={requestId} className="mb-6" />}

        {isServerError && filteredOrders.length > 0 && (
            <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadOrders} />}>
                {error ?? 'No se pudieron cargar las órdenes.'} Se muestran los últimos datos disponibles.
            </Alert>
        )}

        {status === 'loading' ? (
            <OrderListSkeleton count={3} />
        ) : isServerError && filteredOrders.length === 0 ? (
            <ErrorState
                title="No se pudieron cargar las órdenes"
                message={error}
                requestId={requestId}
                onRetry={loadOrders}
            />
        ) : (
            <>
                <div className="space-y-6">
                    {actionable.map((order) => (
                        <OrderAdvanceCard
                            key={order.id}
                            order={order}
                            patente={orderPatente(order, vehicles)}
                            vehicleLabel={orderVehicleLabel(order, vehicles)}
                        />
                    ))}
                    {filteredOrders.length === 0 && (
                        <EmptyState
                            icon={ClipboardList}
                            title={emptyTitle}
                            description={
                                search.trim() || estadoCodigo !== 'all'
                                    ? 'Pruebe con otro término de búsqueda o estado.'
                                    : 'Las órdenes que se le asignen aparecerán aquí para poder avanzar su estado.'
                            }
                        />
                    )}
                </div>

                {closed.length > 0 && (
                    <section className="mt-10">
                        <h3 className="text-lg font-semibold mb-1">Órdenes cerradas</h3>
                        <p className="text-text-muted text-sm mb-4">
                            Sin avances pendientes: las gestiona el cliente o el administrador.
                        </p>
                        <div className="space-y-6">
                            {closed.map((order) => (
                                <ClosedOrderCard
                                    key={order.id}
                                    order={order}
                                    patente={orderPatente(order, vehicles)}
                                    vehicleLabel={orderVehicleLabel(order, vehicles)}
                                />
                            ))}
                        </div>
                    </section>
                )}

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