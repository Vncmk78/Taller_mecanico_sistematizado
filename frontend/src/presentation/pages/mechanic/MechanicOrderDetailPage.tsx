import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ClipboardX, Images } from 'lucide-react';
import { OrderDetailPanel } from '@/presentation/components/orders/OrderDetailPanel';
import { OrderActionsPanel } from '@/presentation/components/orders/OrderActionsPanel';
import { OrderBitacoraSection } from '@/presentation/components/orders/OrderBitacoraSection';
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
import type { ResultadoDisponibilidad } from '@/domain/entities/Inventario';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { EvidenceUploadForm } from '@/presentation/components/evidence/EvidenceUploadForm';
import { EvidenceList } from '@/presentation/components/evidence/EvidenceList';

export function MechanicOrderDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { order, loading, notFound, failed, refetch } = useOrderDetail(id, (oid) =>
        orderService.getOrderById(oid)
    );
    const { presupuesto: presupuestoOrden } = useBudgetDetail(id);
    const { isOffline, error, requestId } = useOrderStore();
    const user = useAuthStore((s) => s.user);
    const vehicles = useVehicleStore((s) => s.vehicles);
    const [evidenciasAbiertas, setEvidenciasAbiertas] = useState(true);
    const [disponibilidad, setDisponibilidad] = useState<ResultadoDisponibilidad | null>(null);
    const [evidenciasRefresh, setEvidenciasRefresh] = useState(0);
    const puedeSubir = user?.role === 'mecanico' || user?.role === 'administrador';

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

    if (loading) {
        return <LoadingState message="Cargando detalle de la orden..." className="p-10" />;
    }

    // El fetch falló y no hay copia local: se muestra un error reintentable en
    // lugar de un "no encontrada" que no es cierto.
    if (failed) {
        return (
            <ErrorState
                className="p-10"
                title="No se pudo cargar el detalle de la orden"
                message={error}
                requestId={requestId}
                onRetry={refetch}
                action={
                    <Link to="/mechanic/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a mis órdenes
                    </Link>
                }
            />
        );
    }

    if (!order || notFound) {
        return (
            <EmptyState
                className="p-10"
                icon={ClipboardX}
                title="Orden no encontrada."
                description="Verifique el número de orden o que siga asignada a su cuenta."
                action={
                    <Link to="/mechanic/ordenes" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                        Volver a mis órdenes
                    </Link>
                }
            />
        );
    }

    return (
        <div className="animate-fade-in p-10">
            <Link
                to="/mechanic/ordenes"
                className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
            >
                <ArrowLeft className="w-4 h-4" /> Volver a mis órdenes
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

            <div className="mt-6">
                <Link
                    to={`/mechanic/ordenes/${order.id}/presupuesto`}
                    className="text-primary-blue text-sm font-medium no-underline hover:underline"
                >
                    Gestionar presupuesto de la orden
                </Link>
            </div>

            {disponibilidad && (
                <section className="card p-6 mt-6" aria-labelledby="disponibilidad-title">
                    <h3 id="disponibilidad-title" className="text-xl font-semibold mb-4">Disponibilidad de repuestos</h3>
                    <p className="text-sm text-text-muted mb-4">
                        {disponibilidad.disponible ? 'Stock suficiente para la orden.' : 'Faltan repuestos para completar la orden.'}
                    </p>
                    <ul className="space-y-2">
                        {disponibilidad.repuestos.map((r) => (
                            <li key={r.repuestoId} className="flex justify-between text-sm">
                                <span>{r.nombre}</span>
                                <span className={r.alcanza ? 'text-status-green' : 'text-status-red'}>
                                    {r.disponible}/{r.requerido} {r.alcanza ? 'OK' : `faltan ${r.faltan}`}
                                </span>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {presupuestoOrden && (presupuestoOrden.versiones?.length ?? 0) > 0 && (
                <section className="card p-6 mt-6" aria-labelledby="mechanic-order-budget-title">
                    <h3 id="mechanic-order-budget-title" className="text-xl font-semibold mb-4">
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

            <OrderBitacoraSection order={order} canWrite={user?.role === 'mecanico'} />

            <section className="card p-6 mt-6" aria-labelledby="mechanic-order-evidence-title">
                <button
                    type="button"
                    onClick={() => setEvidenciasAbiertas((prev) => !prev)}
                    className="w-full flex items-center justify-between gap-4 text-left"
                    aria-expanded={evidenciasAbiertas}
                    aria-controls="mechanic-order-evidence-panel"
                >
                    <h3 id="mechanic-order-evidence-title" className="flex items-center gap-2 text-xl font-semibold">
                        <Images className="h-5 w-5 text-text-muted" aria-hidden />
                        Evidencias
                    </h3>
                    <span className="text-sm text-text-muted">{evidenciasAbiertas ? 'Ocultar' : 'Mostrar'}</span>
                </button>

                {evidenciasAbiertas && (
                    <div id="mechanic-order-evidence-panel" className="mt-6">
                        {puedeSubir && (
                            <EvidenceUploadForm
                                orderId={order.id}
                                className="mb-6 border-b border-border-custom pb-6"
                                onSuccess={() => setEvidenciasRefresh((n) => n + 1)}
                            />
                        )}

                        <EvidenceList ordenId={order.id} refreshKey={evidenciasRefresh} />
                    </div>
                )}
            </section>

            <OrderActionsPanel order={order} className="mt-6" />
        </div>
    );
}