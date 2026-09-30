import { useEffect, useMemo, useState } from 'react';
import { Car, Search } from 'lucide-react';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { VehicleListSkeleton } from '@/presentation/components/vehicles/VehicleListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';

export function MechanicVehiclesPage() {
    const [search, setSearch] = useState('');
    const { vehicles, status, error, isOffline, fetchVehicles } = useVehicleStore();

    const loadVehicles = () => fetchVehicles(() => vehicleService.getAssignedVehicles());

    useEffect(() => {
    loadVehicles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const assignedVehicles = useMemo(() => {
    const term = search.trim().toLowerCase();
    // Online, getAssignedVehicles() ya devuelve solo los vehículos de las
    // órdenes asignadas al mecánico; la caché conserva esa misma respuesta,
    // así que offline no hace falta volver a filtrar por identidad.
    return vehicles.filter((v) =>
        term ? [v.patent, v.brand, v.model].some((field) => field.toLowerCase().includes(term)) : true
        );
    }, [vehicles, search]);

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;

    return (
    <div className="animate-fade-in p-10">
        <h2 className="text-3xl font-bold mb-2">Vehículos en Mis Órdenes Asignadas</h2>
        <p className="text-text-muted mb-6">
        Ficha técnica de solo lectura de los vehículos que tiene actualmente asignados.
        </p>

        <div className="relative w-full sm:w-[320px] mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" aria-hidden="true" />
        <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por patente, marca o modelo..."
            aria-label="Buscar por patente, marca o modelo"
            className="w-full py-2.5 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
        />
        </div>

        {isOffline && <OfflineBanner message={error} onRetry={loadVehicles} className="mb-6" />}

        {isServerError && assignedVehicles.length > 0 && (
        <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={loadVehicles} />}>
            {error ?? 'No se pudieron cargar los vehículos.'} Se muestran los últimos datos disponibles.
        </Alert>
        )}

        {status === 'loading' ? (
        <VehicleListSkeleton count={3} />
        ) : isServerError && assignedVehicles.length === 0 ? (
        <ErrorState
            title="No se pudieron cargar los vehículos"
            message={error}
            onRetry={loadVehicles}
        />
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {assignedVehicles.map((vehicle) => (
            <VehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                ownerName={vehicle.clientId ? `Cliente #${vehicle.clientId}` : undefined}
                detailPath={`/mechanic/vehiculos/${vehicle.id}`}
            />
            ))}
            {assignedVehicles.length === 0 && (
            <EmptyState
                icon={Car}
                title={
                    search.trim()
                        ? `No se encontraron vehículos para "${search}".`
                        : 'No tiene vehículos asignados por el momento.'
                }
                description={
                    search.trim()
                        ? 'Pruebe con otra patente, marca o modelo.'
                        : 'Los vehículos de las órdenes que se le asignen aparecerán aquí.'
                }
            />
            )}
        </div>
        )}
    </div>
    );
}