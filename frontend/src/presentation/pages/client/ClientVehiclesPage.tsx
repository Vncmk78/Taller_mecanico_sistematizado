import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CheckCircle2, Plus, Search } from 'lucide-react';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { VehicleListSkeleton } from '@/presentation/components/vehicles/VehicleListSkeleton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { CURRENT_CLIENT_ID } from '@/infrastructure/mocks/vehicles.mock';

export function ClientVehiclesPage() {
    const location = useLocation();
    const [search, setSearch] = useState('');
    const user = useAuthStore((s) => s.user);
    const { vehicles, status, error, isOffline, fetchVehicles } = useVehicleStore();

    const clientId = user?.id ?? CURRENT_CLIENT_ID;
    const loadVehicles = () => fetchVehicles(() => vehicleService.getMyVehicles(clientId));

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

    return (
    <div className="animate-fade-in">
        <div className="flex justify-between items-center mb-6 gap-4 flex-wrap">
        <div>
            <h2 className="text-3xl font-bold mb-1">Mis Vehículos</h2>
            <p className="text-text-muted">Consulte la ficha técnica y el historial de sus vehículos registrados</p>
        </div>
        <Link
            to="/client/vehiculos/nuevo"
            className="bg-primary-red text-white px-5 py-3 rounded-lg font-bold text-sm flex items-center gap-2 no-underline hover:bg-primary-red-hover transition-colors shrink-0"
        >
            <Plus className="w-4 h-4" /> Añadir vehículo
        </Link>
        </div>

        <div className="relative w-full sm:w-[320px] mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por patente, marca o modelo..."
            className="w-full py-2.5 pl-11 pr-4 bg-black/40 border border-border-custom rounded-lg text-white text-sm outline-none focus:border-primary-red"
        />
        </div>

        {justRegistered && (
        <div className="flex items-center gap-2 mb-6 text-status-green text-sm bg-status-green/10 border border-status-green/40 rounded-lg px-4 py-3">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            Vehículo registrado con éxito.
        </div>
        )}

        {isOffline && <OfflineBanner message={error} onRetry={loadVehicles} className="mb-6" />}

        {status === 'loading' ? (
        <VehicleListSkeleton count={2} />
        ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {myVehicles.map((vehicle) => (
            <VehicleCard key={vehicle.id} vehicle={vehicle} detailPath={`/client/vehiculos/${vehicle.id}`} />
            ))}
            {myVehicles.length === 0 && (
            <p className="text-text-muted col-span-full text-center py-10">
                {search ? `No se encontraron vehículos para "${search}".` : 'Aún no tiene vehículos registrados.'}
            </p>
            )}
        </div>
        )}
    </div>
    );
}