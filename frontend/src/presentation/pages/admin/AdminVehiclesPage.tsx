import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { VehicleListSkeleton } from '@/presentation/components/vehicles/VehicleListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { mockOwners } from '@/infrastructure/mocks/vehicles.mock';

export function AdminVehiclesPage() {
    const [search, setSearch] = useState('');
    const { vehicles, status, error, isOffline, fetchVehicles } = useVehicleStore();

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

    return (
    <div className="animate-fade-in">
        <div className="flex justify-between items-center px-10 pt-10 pb-6">
        <div>
            <h2 className="text-3xl font-bold mb-2 tracking-tight">Catálogo de Vehículos Registrados</h2>
            <p className="text-text-muted text-lg">Trazabilidad completa: fichas técnicas e historial por patente</p>
        </div>
        <div className="relative w-[320px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por patente, marca o modelo..."
            className="w-full py-3 pl-11 pr-4 bg-black/40 border border-border-custom rounded-lg text-white text-sm outline-none focus:border-primary-red"
            />
        </div>
        </div>

        {isOffline && <OfflineBanner message={error} onRetry={loadVehicles} className="mx-10 mb-6" />}

        {status === 'loading' ? (
        <VehicleListSkeleton className="px-10 pb-10" />
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 px-10 pb-10">
            {filtered.map((vehicle) => (
            <VehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                ownerName={mockOwners[vehicle.clientId]?.fullName}
                detailPath={`/admin/vehiculos/${vehicle.id}`}
            />
            ))}
            {filtered.length === 0 && (
            <p className="text-text-muted col-span-full text-center py-10">
                No se encontraron vehículos para "{search}".
            </p>
            )}
        </div>
        )}
    </div>
    );
}