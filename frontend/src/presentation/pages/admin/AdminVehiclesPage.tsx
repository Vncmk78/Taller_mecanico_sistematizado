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

export function AdminVehiclesPage() {
    const [search, setSearch] = useState('');
    const { vehicles, status, error, isOffline, requestId, fetchVehicles } = useVehicleStore();

    const loadVehicles = () => fetchVehicles(() => vehicleService.getAllVehicles());

    useEffect(() => {
    loadVehicles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return vehicles;
    return vehicles.filter((v) =>
        [v.patent, v.brand, v.model].some((field) => field.toLowerCase().includes(term))
    );
    }, [vehicles, search]);

    // El store solo marca isOffline ante fallos de transporte: un error HTTP del
    // servidor se muestra aparte para no rotularlo como "sin conexión".
    const isServerError = status === 'error' && !isOffline;

    return (
    <div className="animate-fade-in">
        <div className="flex justify-between items-center px-10 pt-10 pb-6">
        <div>
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Catálogo de Vehículos Registrados</h2>
            <p className="text-text-muted text-lg">Trazabilidad completa: fichas técnicas e historial por patente</p>
        </div>
        <div className="relative w-[320px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" aria-hidden />
            <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por patente, marca o modelo..."
            aria-label="Buscar por patente, marca o modelo"
            className="w-full py-3 pl-11 pr-4 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue"
            />
        </div>
        </div>

        {isOffline && <OfflineBanner message={error} onRetry={loadVehicles} requestId={requestId} className="mx-10 mb-6" />}

        {isServerError && filtered.length > 0 && (
        <Alert
            tone="error"
            className="mx-10 mb-6"
            action={<RetryButton tone="error" onClick={loadVehicles} />}
        >
            {error ?? 'No se pudieron cargar los vehículos.'} Se muestran los últimos datos disponibles.
        </Alert>
        )}

        {status === 'loading' ? (
        <VehicleListSkeleton className="px-10 pb-10" />
        ) : isServerError && filtered.length === 0 ? (
        <ErrorState
            className="px-10 pb-10"
            title="No se pudieron cargar los vehículos"
            message={error}
            requestId={requestId}
            onRetry={loadVehicles}
        />
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 px-10 pb-10">
            {filtered.map((vehicle) => (
            <VehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                ownerName={vehicle.clientId ? `Cliente #${vehicle.clientId}` : undefined}
                detailPath={`/admin/vehiculos/${vehicle.id}`}
            />
            ))}
            {filtered.length === 0 && (
            <EmptyState
                icon={Car}
                title={
                    search.trim()
                        ? `No se encontraron vehículos para "${search}".`
                        : 'Aún no hay vehículos registrados en el taller.'
                }
                description={
                    search.trim()
                        ? 'Pruebe con otra patente, marca o modelo.'
                        : 'Los vehículos que registre el administrador aparecerán aquí.'
                }
            />
            )}
        </div>
        )}
    </div>
    );
}