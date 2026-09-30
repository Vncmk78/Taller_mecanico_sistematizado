import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { VehicleListSkeleton } from '@/presentation/components/vehicles/VehicleListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { mockAssignedVehicleIds, mockOwners } from '@/infrastructure/mocks/vehicles.mock';

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
    // órdenes asignadas al mecánico; el filtro por mock es solo para el modo
    // offline (caché con datos de demo).
    const base = isOffline
        ? vehicles.filter((v) => mockAssignedVehicleIds.includes(v.id))
        : vehicles;
    return base.filter((v) =>
        term ? [v.patent, v.brand, v.model].some((field) => field.toLowerCase().includes(term)) : true
        );
    }, [vehicles, search, isOffline]);

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

        {status === 'loading' ? (
        <VehicleListSkeleton count={3} />
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {assignedVehicles.map((vehicle) => (
            <VehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                ownerName={vehicle.clientId ? mockOwners[vehicle.clientId]?.fullName : undefined}
                detailPath={`/mechanic/vehiculos/${vehicle.id}`}
            />
            ))}
            {assignedVehicles.length === 0 && (
            <p className="text-text-muted col-span-full text-center py-10">
                {search
                ? `No se encontraron vehículos para "${search}".`
                : 'No tiene vehículos asignados por el momento.'}
            </p>
            )}
        </div>
        )}
    </div>
    );
}