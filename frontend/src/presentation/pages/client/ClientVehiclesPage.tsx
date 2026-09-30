import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Car, Plus, Search } from 'lucide-react';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { VehicleListSkeleton } from '@/presentation/components/vehicles/VehicleListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';

export function ClientVehiclesPage() {
    const location = useLocation();
    const [search, setSearch] = useState('');
    const user = useAuthStore((s) => s.user);
    const { vehicles, status, error, isOffline, fetchVehicles } = useVehicleStore();

    // Identidad real de la sesión (usuario_id de MS1): la Gateway ya limita
    // GET /vehiculos al cliente autenticado, y este id se usa para resolver la
    // pertenencia de cada ficha en la caché compartida entre portales.
    const clientId = user?.id;
    const loadVehicles = () => {
    if (!clientId) return;
    fetchVehicles(() => vehicleService.getMyVehicles(clientId));
    };

    useEffect(() => {
    loadVehicles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const myVehicles = useMemo(() => {
    const term = search.trim().toLowerCase();
    return vehicles
        .filter((v) => v.clientId === clientId)
        .filter((v) =>
        term ? [v.patent, v.brand, v.model].some((field) => field.toLowerCase().includes(term)) : true
        );
    }, [vehicles, clientId, search]);

    const justRegistered = Boolean((location.state as { justRegistered?: boolean } | null)?.justRegistered);

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;

    return (
    <div className="animate-fade-in">
        <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
        <div>
            <h2 className="text-3xl font-bold mb-1">Mis Vehículos</h2>
            <p className="text-text-muted">Consulte la ficha técnica y el historial de sus vehículos registrados</p>
        </div>
        <Link
            to="/client/vehiculos/nuevo"
            className="bg-primary-blue text-white px-5 py-3 rounded-lg font-bold text-sm flex items-center gap-2 no-underline hover:bg-primary-blue-hover transition-colors shrink-0"
        >
            <Plus className="w-4 h-4" /> Añadir vehículo
        </Link>
        </div>

        <div className="relative w-full sm:w-[320px] mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" aria-hidden />
        <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por patente, marca o modelo..."
            aria-label="Buscar por patente, marca o modelo"
            className="w-full py-2.5 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
        />
        </div>

        {justRegistered && (
        <Alert tone="success" className="mb-6">
          Vehículo registrado con éxito.
        </Alert>
        )}

        {isOffline && <OfflineBanner message={error} onRetry={loadVehicles} className="mb-6" />}

        {isServerError && myVehicles.length > 0 && (
        <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadVehicles} />}>
            {error ?? 'No se pudieron cargar sus vehículos.'} Se muestran los últimos datos disponibles.
        </Alert>
        )}

        {status === 'loading' ? (
        <VehicleListSkeleton count={2} />
        ) : isServerError && myVehicles.length === 0 ? (
        <ErrorState
            title="No se pudieron cargar sus vehículos"
            message={error}
            onRetry={loadVehicles}
            action={
            <Link
                to="/client/vehiculos/nuevo"
                className="text-primary-blue text-sm font-medium no-underline hover:underline"
            >
                Registrar un vehículo
            </Link>
            }
        />
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {myVehicles.map((vehicle) => (
            <VehicleCard key={vehicle.id} vehicle={vehicle} detailPath={`/client/vehiculos/${vehicle.id}`} />
            ))}
            {myVehicles.length === 0 && (
            <EmptyState
                icon={Car}
                title={
                    search.trim()
                        ? `No se encontraron vehículos para "${search}".`
                        : 'Aún no tiene vehículos registrados.'
                }
                description={
                    search.trim()
                        ? 'Pruebe con otra patente, marca o modelo.'
                        : 'Registre su primer vehículo para poder agendar mantenciones.'
                }
                action={
                    !search.trim() && (
                    <Link
                        to="/client/vehiculos/nuevo"
                        className="bg-primary-blue text-white px-4 py-2 rounded-lg font-medium text-sm no-underline hover:bg-primary-blue-hover transition-colors"
                    >
                        Registrar vehículo
                    </Link>
                    )
                }
            />
            )}
        </div>
        )}
    </div>
    );
}