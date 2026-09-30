import { useEffect, useState } from 'react';
import { Check, ClipboardList } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { AVANCES_MECANICO, ESTADOS_ORDEN } from '@/domain/entities/Order';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { OrderStateStepper } from '@/presentation/components/orders/OrderStateStepper';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';

interface OrderAdvanceCardProps {
    order: Order;
    patente?: string;
    vehicleLabel?: string | null;
}

function OrderAdvanceCard({ order, patente, vehicleLabel }: OrderAdvanceCardProps) {
    const [destino, setDestino] = useState('');
    const [observacion, setObservacion] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const updateOrder = useOrderStore((s) => s.updateOrder);

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
            setDestino('');
            setObservacion('');
        } catch (err) {
            setError(getApiErrorMessage(err, 'No se pudo actualizar el estado de la orden.'));
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
                        {vehicleLabel ?? `Vehículo N°${order.vehicleId}`}
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

            {avances.length === 0 ? (
                <p className="text-text-muted text-sm mt-4">
                    Sin avances disponibles para el estado actual.
                </p>
            ) : (
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
                        isLoading={submitting}
                        disabled={!destino}
                        onClick={confirmarAvance}
                        className="shrink-0"
                    >
                        <span className="flex items-center gap-2">
                            <Check className="w-4 h-4" /> Confirmar avance
                        </span>
                    </Button>
                </div>
            )}

            {error && <Alert tone="error" className="mt-4">{error}</Alert>}
        </div>
    );
}

export function MechanicStatusPage() {
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

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;

    return (
        <div className="animate-fade-in p-10">
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Actualizar Estados</h2>
            <p className="text-text-muted text-lg mb-8">Mantén el flujo de las órdenes al día</p>

            {isOffline && <OfflineBanner message={error} onRetry={loadOrders} requestId={requestId} className="mb-6" />}

            {isServerError && myOrders.length > 0 && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadOrders} />}>
                    {error ?? 'No se pudieron cargar las órdenes.'} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            {status === 'loading' ? (
                <OrderListSkeleton count={3} />
            ) : isServerError && myOrders.length === 0 ? (
                <ErrorState
                    title="No se pudieron cargar las órdenes"
                    message={error}
                    requestId={requestId}
                    onRetry={loadOrders}
                />
            ) : (
                <div className="space-y-6">
                    {myOrders.map((order) => (
                        <OrderAdvanceCard
                            key={order.id}
                            order={order}
                            patente={orderPatente(order, vehicles)}
                            vehicleLabel={orderVehicleLabel(order, vehicles)}
                        />
                    ))}
                    {myOrders.length === 0 && (
                        <EmptyState
                            icon={ClipboardList}
                            title="No tiene órdenes asignadas por el momento."
                            description="Las órdenes que se le asignen aparecerán aquí para poder avanzar su estado."
                        />
                    )}
                </div>
            )}
        </div>
    );
}