import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { VehicleCard } from '@/presentation/components/vehicles/VehicleCard';
import { mockAssignedVehicleIds, mockOwners } from '@/infrastructure/mocks/vehicles.mock';

export function MechanicVehiclesPage() {
    const vehicles = useVehicleStore((s) => s.vehicles);
    const assignedVehicles = vehicles.filter((v) => mockAssignedVehicleIds.includes(v.id));

    return (
    <div className="animate-fade-in p-10">
        <h2 className="text-3xl font-bold mb-2">Vehículos en Mis Órdenes Asignadas</h2>
        <p className="text-text-muted mb-8">
        Ficha técnica de solo lectura de los vehículos que tiene actualmente asignados.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {assignedVehicles.map((vehicle) => (
            <VehicleCard
            key={vehicle.id}
            vehicle={vehicle}
            ownerName={mockOwners[vehicle.clientId]?.fullName}
            detailPath={`/mechanic/vehiculos/${vehicle.id}`}
            />
        ))}
        {assignedVehicles.length === 0 && (
            <p className="text-text-muted col-span-full text-center py-10">
            No tiene vehículos asignados por el momento.
            </p>
        )}
        </div>
    </div>
    );
}