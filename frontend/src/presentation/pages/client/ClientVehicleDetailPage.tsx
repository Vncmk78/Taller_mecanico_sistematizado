import { useEffect, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CalendarPlus, ClipboardList, SearchX } from 'lucide-react';
import { VehicleInfoPanel } from '@/presentation/components/vehicles/VehicleInfoPanel';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { formatDate } from '@/presentation/utils/orderDisplay';
import { useVehicleDetail } from '@/presentation/hooks/useVehicleDetail';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { orderService } from '@/infrastructure/api/OrderService';

export function ClientVehicleDetailPage() {
    const { id } = useParams<{ id: string }>();
    const user = useAuthStore((s) => s.user);
    // Identidad real de la sesión (usuario_id de MS1) para resolver la
    // pertenencia del vehículo en la caché compartida entre portales.
    const clientId = user?.id;
    const { vehicle, loading, notFound, failed, refetch } = useVehicleDetail(id, (vid) =>
        vehicleService.getVehicleById(vid, clientId)
    );
    const { isOffline, error, requestId } = useVehicleStore();
    const vehicles = useVehicleStore((s) => s.vehicles);
    const {
        orders,
        status: ordersStatus,
        error: ordersError,
        fetchOrders,
    } = useOrderStore();
    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const vehicleOrders = useMemo(
        () =>
            [...orders]
                .filter((o) => o.vehicleId === id)
                .sort((a, b) => (a.actualizadoEn < b.actualizadoEn ? 1 : -1)),
        [orders, id]
    );

    if (loading) {
        return <LoadingState message="Cargando ficha del vehículo..." className="p-10" />;
    }

    // El fetch falló y no hay copia local: se muestra un error reintentable en
    // lugar de un "no encontrado" que no es cierto.
    if (failed) {
        return (
            <ErrorState
                className="p-10"
                title="No se pudo cargar la ficha del vehículo"
                message={error}
                requestId={requestId}
                onRetry={refetch}
                action={
                    <Link to="/client/vehiculos" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a mis vehículos
                    </Link>
                }
            />
        );
    }

    // Ownership check: aunque el vehículo exista en caché, no es tuyo si el clientId no calza.
    if (!vehicle || notFound || vehicle.clientId !== clientId) {
        return (
            <EmptyState
                className="p-10"
                icon={SearchX}
                title="Vehículo no encontrado o no pertenece a su cuenta."
                description="Verifique la patente o que el vehículo siga registrado a su nombre."
                action={
                    <Link to="/client/vehiculos" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a mis vehículos
                    </Link>
                }
            />
        );
    }

    const ordersServerError = ordersStatus === 'error';

    return (
        <div className="p-10 animate-fade-in">
            <Link
                to="/client/vehiculos"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a mis vehículos
            </Link>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />}

            {/* Error del servidor con copia local en caché: se conserva la ficha y se avisa. */}
            {!isOffline && error && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
                    {error} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-6">
                <div className="flex flex-col gap-4">
                    <VehicleInfoPanel vehicle={vehicle} />
                    <Link
                        to="/client/agendar"
                        className="bg-primary-blue text-white py-3 rounded-lg font-bold text-center flex items-center justify-center gap-2 no-underline hover:bg-primary-blue-hover transition-colors"
                    >
                        <CalendarPlus className="w-4 h-4" /> Agendar mantención para este vehículo
                    </Link>
                </div>

                <div className="card">
                    <h3 className="text-xl font-semibold flex items-center justify-between gap-2 mb-4 pb-4 border-b border-border-custom">
                        <span className="flex items-center gap-2">
                            <ClipboardList className="w-5 h-5 text-text-muted" aria-hidden />
                            Historial de Órdenes
                        </span>
                        {vehicleOrders.length > 0 && (
                            <span className="text-sm font-normal text-text-muted">
                                {vehicleOrders.length} {vehicleOrders.length === 1 ? 'orden' : 'órdenes'}
                            </span>
                        )}
                    </h3>

                    {ordersStatus === 'loading' ? (
                        <p className="text-text-muted text-sm py-6 text-center">
                            Cargando historial de mantención...
                        </p>
                    ) : ordersServerError ? (
                        <Alert tone="error" action={<RetryButton tone="error" onClick={loadOrders} />}>
                            {ordersError ?? 'No se pudieron cargar las órdenes del vehículo.'}
                        </Alert>
                    ) : vehicleOrders.length === 0 ? (
                        <p className="text-text-muted text-sm py-6 text-center">
                            Este vehículo aún no tiene órdenes de trabajo registradas.
                        </p>
                    ) : (
                        <ul className="flex flex-col gap-3" aria-label="Historial de órdenes del vehículo">
                            {vehicleOrders.map((order) => {
                                const vehicleMatch = vehicles.find((v) => v.id === order.vehicleId);
                                return (
                                    <li key={order.id}>
                                        <Link
                                            to={`/client/ordenes/${order.id}`}
                                            className="flex items-center justify-between gap-3 bg-bg-secondary rounded-lg px-4 py-3 hover:bg-surface no-underline transition-colors"
                                        >
                                            <div className="min-w-0">
                                                <p className="text-text-main font-semibold truncate">
                                                    Orden n° {order.id}
                                                    {vehicleMatch ? ` · ${vehicleMatch.brand} ${vehicleMatch.model}` : ''}
                                                </p>
                                                <p className="text-text-muted text-sm">
                                                    Actualizada el {formatDate(order.actualizadoEn)}
                                                </p>
                                            </div>
                                            <OrderStatusBadge
                                                estadoCodigo={order.estadoCodigo}
                                                variant="dot"
                                                size="sm"
                                                className="shrink-0"
                                            />
                                        </Link>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>
            </div>
        </div>
    );
}