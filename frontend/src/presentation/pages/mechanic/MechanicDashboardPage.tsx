import { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Car, ClipboardList, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { ESTADOS_ORDEN, AVANCES_MECANICO } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { OrderListSkeleton } from '@/presentation/components/orders/OrderListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { filterOrdersByMechanic, filterVehiclesByOrders } from '@/presentation/utils/mechanicScope';

interface KpiCardProps {
    label: string;
    value: number;
    icon: ReactNode;
    accent: string;
}

/** Estados finales: la orden ya no avanza dentro del taller. */
const ESTADOS_CERRADOS = [7, 8];

function KpiCard({ label, value, icon, accent }: KpiCardProps) {
    return (
        <div className="card p-6">
            <div className="flex items-center gap-3 mb-3">
                <span className={`p-2 rounded-lg ${accent}`} aria-hidden="true">
                    {icon}
                </span>
                <span className="text-sm text-text-muted">{label}</span>
            </div>
            <p className="text-3xl font-bold">{value}</p>
        </div>
    );
}

export function MechanicDashboardPage() {
    const { orders, status, error, isOffline, requestId, fetchOrders } = useOrderStore();
    const { vehicles: allVehicles, fetchVehicles } = useVehicleStore();
    const mechanicId = useAuthStore((s) => s.user?.id);

    const loadOrders = () => fetchOrders(() => orderService.getOrders());

    useEffect(() => {
        loadOrders();
        fetchVehicles(() => vehicleService.getAssignedVehicles());
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const myOrders = filterOrdersByMechanic(orders, mechanicId);
    const vehicles = filterVehiclesByOrders(allVehicles, myOrders);

    // GET /api/ordenes devuelve la colección completa sin filtros ni paginación,
    // así que los indicadores se calculan en el cliente sobre la caché.
    const kpis = useMemo(() => {
        const cerradas = myOrders.filter((o) => ESTADOS_CERRADOS.includes(o.estadoCodigo)).length;
        return {
            total: myOrders.length,
            activas: myOrders.length - cerradas,
            pendientes: myOrders.filter((o) => (AVANCES_MECANICO[o.estadoCodigo]?.length ?? 0) > 0).length,
            vehiculos: vehicles.length,
        };
    }, [myOrders, vehicles]);

    const isServerError = status === 'error' && !isOffline;

    if (status === 'loading') {
        return (
            <div className="animate-fade-in p-10">
                <h2 className="text-3xl font-bold mb-2">Panel del Mecánico</h2>
                <p className="text-text-muted mb-6">Resumen de tus órdenes asignadas</p>
                <OrderListSkeleton count={2} />
            </div>
        );
    }

    if (isServerError && myOrders.length === 0) {
        return (
            <div className="animate-fade-in p-10">
                <ErrorState
                    title="No se pudieron cargar tus órdenes"
                    message={error}
                    requestId={requestId}
                    onRetry={loadOrders}
                />
            </div>
        );
    }

    return (
    <div className="animate-fade-in p-10">
        <h2 className="text-3xl font-bold mb-2">Panel del Mecánico</h2>
        <p className="text-text-muted mb-6">Resumen de tus órdenes asignadas</p>

        {isOffline && <OfflineBanner message={error} onRetry={loadOrders} requestId={requestId} className="mb-6" />}

        {isServerError && myOrders.length > 0 && (
            <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadOrders} />}>
                {error ?? 'No se pudieron cargar las órdenes.'} Se muestran los últimos datos disponibles.
            </Alert>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <KpiCard label="Órdenes asignadas" value={kpis.total} icon={<ClipboardList className="w-5 h-5" />} accent="bg-primary-blue/10 text-primary-blue" />
            <KpiCard label="Órdenes activas" value={kpis.activas} icon={<RefreshCw className="w-5 h-5" />} accent="bg-status-yellow/10 text-status-yellow" />
            <KpiCard label="Esperan tu avance" value={kpis.pendientes} icon={<AlertTriangle className="w-5 h-5" />} accent="bg-status-orange/10 text-status-orange" />
            <KpiCard label="Vehículos asignados" value={kpis.vehiculos} icon={<Car className="w-5 h-5" />} accent="bg-status-green/10 text-status-green" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
            <Link
                to="/mechanic/estados"
                className="card p-6 flex items-center justify-between no-underline hover:border-primary-blue transition-colors"
            >
                <div>
                    <h3 className="text-lg font-semibold">Actualizar estados</h3>
                    <p className="text-text-muted text-sm">
                        {kpis.pendientes > 0
                            ? `${kpis.pendientes} ${kpis.pendientes === 1 ? 'orden espera' : 'órdenes esperan'} tu avance.`
                            : 'No tienes avances pendientes por ahora.'}
                    </p>
                </div>
                <RefreshCw className="w-5 h-5 text-text-muted shrink-0" />
            </Link>
            <Link
                to="/mechanic/ordenes"
                className="card p-6 flex items-center justify-between no-underline hover:border-primary-blue transition-colors"
            >
                <div>
                    <h3 className="text-lg font-semibold">Mis órdenes</h3>
                    <p className="text-text-muted text-sm">Consulta el detalle y el historial de cada orden.</p>
                </div>
                <ClipboardList className="w-5 h-5 text-text-muted shrink-0" />
            </Link>
        </div>

        {myOrders.length === 0 ? (
            <EmptyState
                icon={ClipboardList}
                title="No tiene órdenes asignadas por el momento."
                description="Las órdenes que se le asignen aparecerán aquí con su estado actual."
            />
        ) : (
            <div className="card p-6">
                <h3 className="text-lg font-semibold mb-4">Órdenes por estado</h3>
                <ul className="flex flex-col gap-2">
                    {Object.entries(ESTADOS_ORDEN).map(([codigo, etiqueta]) => {
                    const count = myOrders.filter((o) => o.estadoCodigo === Number(codigo)).length;
                    if (count === 0) return null;
                    return (
                        <li key={codigo} className="flex items-center justify-between text-sm">
                            <span className="text-text-muted">{etiqueta}</span>
                            <span className="font-semibold">{count}</span>
                        </li>
                    );
                    })}
                </ul>
            </div>
        )}
    </div>
    );
}