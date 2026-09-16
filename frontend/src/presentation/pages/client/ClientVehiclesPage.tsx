import { Link, useLocation } from 'react-router-dom';
import { CheckCircle2, Plus } from 'lucide-react';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { CURRENT_CLIENT_ID } from '@/infrastructure/mocks/vehicles.mock';

export function ClientVehiclesPage() {
    const location = useLocation();
    const user = useAuthStore((s) => s.user);
    const vehicles = useVehicleStore((s) => s.vehicles);

    const clientId = user?.id ?? CURRENT_CLIENT_ID;
    const myVehicles = vehicles.filter((v) => v.clientId === clientId);
    const justRegistered = Boolean((location.state as { justRegistered?: boolean } | null)?.justRegistered);

    return (
    <div className="animate-fade-in">
        <div className="flex justify-between items-center mb-8">
        <div>
            <h2 className="text-3xl font-bold mb-1">Mis Vehículos</h2>
            <p className="text-text-muted">Consulte la ficha técnica y el historial de sus vehículos registrados</p>
        </div>
        <Link
            to="/client/vehiculos/nuevo"
            className="bg-primary-red text-white px-5 py-3 rounded-lg font-bold text-sm flex items-center gap-2 no-underline hover:bg-primary-red-hover transition-colors"
        >
            <Plus className="w-4 h-4" /> Añadir vehículo
        </Link>
        </div>

        {justRegistered && (
        <div className="flex items-center gap-2 mb-6 text-status-green text-sm bg-status-green/10 border border-status-green/40 rounded-lg px-4 py-3">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            Vehículo registrado con éxito.
        </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {myVehicles.map((vehicle) => (
            <VehicleCard key={vehicle.id} vehicle={vehicle} detailPath={`/client/vehiculos/${vehicle.id}`} />
        ))}
        {myVehicles.length === 0 && (
            <p className="text-text-muted col-span-full text-center py-10">
            Aún no tiene vehículos registrados.
            </p>
        )}
        </div>
    </div>
    );
}