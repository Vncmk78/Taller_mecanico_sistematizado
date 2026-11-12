import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ClipboardX, Images } from 'lucide-react';
import { OrderDetailPanel } from '@/presentation/components/orders/OrderDetailPanel';
import { OrderActionsPanel } from '@/presentation/components/orders/OrderActionsPanel';
import { DevolucionVehiculoPanel } from '@/presentation/components/orders/DevolucionVehiculoPanel';
import { OrderStatusAndHistory } from '@/presentation/components/orders/OrderStatusAndHistory';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { orderPatente, orderVehicleLabel } from '@/presentation/utils/orderDisplay';
import { useOrderDetail } from '@/presentation/hooks/useOrderDetail';
import { useBudgetDetail } from '@/presentation/hooks/useBudgetDetail';
import { BudgetItemRow } from '@/presentation/components/budgets/BudgetItemRow';
import { BudgetStatusBadge } from '@/presentation/components/budgets/BudgetStatusBadge';
import { orderService } from '@/infrastructure/api/OrderService';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import type { ResultadoDisponibilidad } from '@/domain/entities/Inventario';
import type { Order } from '@/domain/entities/Order';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { EvidenceUploadForm } from '@/presentation/components/evidence/EvidenceUploadForm';
import { EvidenceList } from '@/presentation/components/evidence/EvidenceList';

export function AdminOrderDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { order, loading, notFound, failed, refetch } = useOrderDetail(id, (oid) =>
        orderService.getOrderById(oid)
    );
    const { presupuesto: presupuestoOrden } = useBudgetDetail(id);
    const { isOffline, error, requestId } = useOrderStore();
    const updateOrder = useOrderStore((s) => s.updateOrder);
    const refreshOrderHistory = useOrderHistoryStore((s) => s.fetchOrderHistory);
    const vehicles = useVehicleStore((s) => s.vehicles);
    const [evidenciasAbiertas, setEvidenciasAbiertas] = useState(true);
    const [evidenciasRefresh, setEvidenciasRefresh] = useState(0);
    const [disponibilidad, setDisponibilidad] = useState<ResultadoDisponibilidad | null>(null);
    const [stockActionError, setStockActionError] = useState<string | null>(null);
    const [stockActionSuccess, setStockActionSuccess] = useState<string | null>(null);
    const [stockSubmitting, setStockSubmitting] = useState(false);

    useEffect(() => {
        if (!order?.id) return;
        let active = true;
        inventarioService
            .getDisponibilidadOrden(Number(order.id))
            .then((result) => {
                if (active) setDisponibilidad(result);
            })
            .catch(() => {
                if (active) setDisponibilidad(null);
            });
        return () => {
            active = false;
        };
    }, [order?.id]);

    const handleReservar = async () => {
        if (!order?.id) return;
        setStockSubmitting(true);
        setStockActionError(null);
        setStockActionSuccess(null);
        try {
            const result = await inventarioService.reservar(Number(order.id));
            setStockActionSuccess(result.reservado ? 'Stock reservado correctamente.' : 'No se pudo reservar todo el stock.');
            if (!result.reservado && result.faltantes.length) {
                setStockActionError(`Faltan: ${result.faltantes.map((f) => `${f.nombre} (${f.faltan})`).join(', ')}`);
            }
            const disp = await inventarioService.getDisponibilidadOrden(Number(order.id));
            setDisponibilidad(disp);
        } catch (err) {
            const faltantes = (err as { response?: { data?: { faltantes?: Array<{ nombre: string; faltan: number }> } } })?.response?.data?.faltantes;
            if (faltantes?.length) {
                setStockActionError(`Stock insuficiente: ${faltantes.map((f) => `${f.nombre} (${f.faltan})`).join(', ')}`);
            } else {
                setStockActionError(getApiErrorMessage(err, 'No se pudo reservar el stock.'));
            }
        } finally {
            setStockSubmitting(false);
        }
    };

    const handleConfirmarDisponibilidad = async () => {
        if (!order?.id) return;
        const orderId = Number(order.id);
        setStockSubmitting(true);
        setStockActionError(null);
        setStockActionSuccess(null);
        try {
            await inventarioService.confirmarDisponibilidad(orderId);
            const actualizado = await recargarOrdenYStock(orderId);
            if (actualizado?.estadoCodigo === 5) {
                setStockActionSuccess('Disponibilidad confirmada y orden en reparación.');
            } else if (!actualizado) {
                setStockActionSuccess('Disponibilidad confirmada. No se pudo actualizar el detalle de la orden.');
            } else {
                setStockActionSuccess('Disponibilidad confirmada. Se actualizó la orden y el historial.');
            }
        } catch (err) {
            const response = (err as {
                response?: {
                    status?: number;
                    data?: { detail?: string | { mensaje?: string; faltantes?: Array<{ repuesto_id: number; requerido: number; disponible: number }> } };
                };
            })?.response;
            const faltantes = typeof response?.data?.detail === 'object'
                ? response.data.detail.faltantes
                : undefined;

            if (response?.status === 409 && faltantes?.length) {
                const detalle = faltantes.map((f) => {
                    const nombre = disponibilidad?.repuestos.find((r) => r.repuestoId === f.repuesto_id)?.nombre
                        ?? `Repuesto ${f.repuesto_id}`;
                    return `${nombre} (faltan ${Math.max(0, f.requerido - f.disponible)})`;
                }).join(', ');
                setStockActionError(`Stock insuficiente: ${detalle}`);
                try {
                    setDisponibilidad(await inventarioService.getDisponibilidadOrden(orderId));
                } catch {
                    // Se conserva el detalle del 409 si el refresco de stock también falla.
                }
            } else if (response?.status === 503 || !response?.status) {
                const actualizado = await recargarOrdenYStock(orderId);
                if (actualizado?.estadoCodigo === 5) {
                    setStockActionSuccess('La confirmación se aplicó y la orden ya está en reparación.');
                } else {
                    setStockActionError('No se pudo confirmar la respuesta del servidor. La reserva pudo quedar registrada; reintentar es seguro.');
                }
            } else {
                setStockActionError(getApiErrorMessage(err, 'No se pudo confirmar la disponibilidad de repuestos.'));
            }
        } finally {
            setStockSubmitting(false);
        }
    };

    const recargarOrdenYStock = async (orderId: number) => {
        const orderIdString = String(orderId);
        const [orderResult, , availabilityResult] = await Promise.allSettled([
            orderService.getOrderById(orderIdString),
            refreshOrderHistory(orderIdString, orderService.getOrderHistory),
            inventarioService.getDisponibilidadOrden(orderId),
        ]);
        let actualizado: Order | undefined;
        if (orderResult.status === 'fulfilled') {
            actualizado = orderResult.value;
            updateOrder(actualizado);
        }
        if (availabilityResult.status === 'fulfilled') setDisponibilidad(availabilityResult.value);
        return actualizado;
    };

    const handleLiberar = async () => {
        if (!order?.id) return;
        setStockSubmitting(true);
        setStockActionError(null);
        setStockActionSuccess(null);
        try {
            await inventarioService.liberar(Number(order.id), crypto.randomUUID());
            setStockActionSuccess('Reserva liberada correctamente.');
            const disp = await inventarioService.getDisponibilidadOrden(Number(order.id));
            setDisponibilidad(disp);
        } catch (err) {
            setStockActionError(getApiErrorMessage(err, 'No se pudo liberar la reserva.'));
        } finally {
            setStockSubmitting(false);
        }
    };

    if (loading) {
        return <LoadingState message="Cargando detalle de la orden..." className="p-4 sm:p-6 lg:p-10" />;
    }

    // El fetch falló y no hay copia local: se muestra un error reintentable en
    // lugar de un "no encontrada" que no es cierto.
    if (failed) {
        return (
            <ErrorState
                className="p-4 sm:p-6 lg:p-10"
                title="No se pudo cargar el detalle de la orden"
                message={error}
                requestId={requestId}
                onRetry={refetch}
                action={
                    <Link to="/admin/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a la gestión de órdenes
                    </Link>
                }
            />
        );
    }

    if (!order || notFound) {
        return (
            <EmptyState
                className="p-4 sm:p-6 lg:p-10"
                icon={ClipboardX}
                title="Orden no encontrada."
                description="Verifique el número de orden o que la orden siga disponible."
                action={
                    <Link
                        to="/admin/ordenes"
                        className="text-primary-blue text-sm font-medium no-underline hover:underline"
                    >
                        Volver a la gestión de órdenes
                    </Link>
                }
            />
        );
    }

    return (
        <div className="animate-fade-in p-4 sm:p-6 lg:p-10">
            <Link
                to="/admin/ordenes"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a la gestión de órdenes
            </Link>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />}

            {/* Error del servidor con copia local en caché: se conserva la orden y se avisa. */}
            {!isOffline && error && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
                    {error} Se muestran los últimos datos disponibles.
                </Alert>
            )}

            <OrderDetailPanel
                order={order}
                patente={orderPatente(order, vehicles)}
                vehicleLabel={orderVehicleLabel(order, vehicles)}
            />

            <OrderStatusAndHistory order={order} />
            <Link className="btn btn-primary inline-flex my-4" to={`/admin/ordenes/${order.id}/presupuesto`}>
                Revisar presupuesto y precios
            </Link>

            {presupuestoOrden && (presupuestoOrden.versiones?.length ?? 0) > 0 && (
                <section className="card p-6 mt-6" aria-labelledby="admin-order-budget-title">
                    <h3 id="admin-order-budget-title" className="text-xl font-semibold mb-4">
                        Presupuesto (líneas)
                    </h3>
                    <BudgetStatusBadge estado={presupuestoOrden.estadoUltimaVersion} />
                    <div className="flex flex-col gap-3 mt-4">
                        {(presupuestoOrden.versiones[presupuestoOrden.versiones.length - 1]?.items ?? []).map((item) => (
                            <BudgetItemRow key={item.id} item={item} />
                        ))}
                    </div>
                </section>
            )}

            {(disponibilidad || order.estadoCodigo === 4) && (
                <section className="card p-6 mt-6" aria-labelledby="admin-order-stock-title">
                    <h3 id="admin-order-stock-title" className="text-xl font-semibold mb-4">Disponibilidad de repuestos</h3>
                    {disponibilidad ? (
                        <>
                            <p className="text-sm text-text-muted mb-4">
                                {disponibilidad.disponible ? 'Stock suficiente para la orden.' : 'Faltan repuestos para completar la orden.'}
                            </p>
                            <ul className="space-y-2 mb-4">
                                {disponibilidad.repuestos.map((r) => (
                                    <li key={r.repuestoId} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm">
                                        <span>{r.nombre}</span>
                                        <span className={r.alcanza ? 'text-status-green' : 'text-status-red'}>
                                            {r.disponible}/{r.requerido} {r.alcanza ? 'OK' : `faltan ${r.faltan}`}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </>
                    ) : (
                        <p className="text-sm text-text-muted mb-4">No se pudo cargar la disponibilidad actual.</p>
                    )}
                    {stockActionError && <p className="text-status-red text-sm mb-3">{stockActionError}</p>}
                    {stockActionSuccess && <p className="text-status-green text-sm mb-3">{stockActionSuccess}</p>}
                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={order.estadoCodigo === 4 ? handleConfirmarDisponibilidad : handleReservar}
                            disabled={stockSubmitting}
                            className="px-4 py-2 rounded-lg bg-primary-blue text-white text-sm font-medium disabled:opacity-50"
                        >
                            {stockSubmitting
                                ? 'Procesando...'
                                : order.estadoCodigo === 4
                                  ? 'Confirmar disponibilidad y pasar a reparación'
                                  : 'Reservar stock'}
                        </button>
                        <button
                            type="button"
                            onClick={handleLiberar}
                            disabled={stockSubmitting}
                            className="px-4 py-2 rounded-lg border border-border-custom text-sm font-medium disabled:opacity-50"
                        >
                            Liberar reserva
                        </button>
                    </div>
                </section>
            )}

            <section className="card p-6 mt-6" aria-labelledby="admin-order-evidence-title">
                <button
                    type="button"
                    onClick={() => setEvidenciasAbiertas((prev) => !prev)}
                    className="w-full flex items-center justify-between gap-4 text-left"
                    aria-expanded={evidenciasAbiertas}
                    aria-controls="admin-order-evidence-panel"
                >
                    <h3 id="admin-order-evidence-title" className="flex items-center gap-2 text-xl font-semibold">
                        <Images className="h-5 w-5 text-text-muted" aria-hidden />
                        Evidencias
                    </h3>
                    <span className="text-sm text-text-muted">{evidenciasAbiertas ? 'Ocultar' : 'Mostrar'}</span>
                </button>

                {evidenciasAbiertas && (
                    <div id="admin-order-evidence-panel" className="mt-6">
                        <EvidenceUploadForm
                            orderId={order.id}
                            className="mb-6 border-b border-border-custom pb-6"
                            onSuccess={() => setEvidenciasRefresh((n) => n + 1)}
                        />

                        <EvidenceList ordenId={order.id} refreshKey={evidenciasRefresh} />
                    </div>
                )}
            </section>

            <DevolucionVehiculoPanel key={order.id} order={order} className="mt-6" />

            <OrderActionsPanel order={order} className="mt-6" />
        </div>
    );
}
