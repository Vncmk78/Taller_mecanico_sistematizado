import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ClipboardList } from 'lucide-react';
import { VehicleInfoPanel } from '@/presentation/components/vehicles/VehicleInfoPanel';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { mockOwners } from '@/infrastructure/mocks/vehicles.mock';

export function AdminVehicleDetailPage() {
    const { id } = useParams<{ id: string }>();
    const vehicles = useVehicleStore((s) => s.vehicles);
    const vehicle = vehicles.find((v) => v.id === id);

    if (!vehicle) {
    return (
        <div className="p-10 text-text-muted">
        Vehículo no encontrado.{' '}
        <Link to="/admin/vehiculos" className="text-primary-red">Volver al catálogo</Link>
        </div>
    );
    }

    return (
    <div className="animate-fade-in p-10">
        <Link
        to="/admin/vehiculos"
        className="inline-flex items-center gap-2 text-text-muted hover:text-white mb-6 no-underline"
        >
        <ArrowLeft className="w-4 h-4" /> Volver al catálogo
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-6">
        <VehicleInfoPanel vehicle={vehicle} owner={mockOwners[vehicle.clientId]} />

        <div className="glass-card">
            <h3 className="text-xl font-semibold flex items-center gap-2 mb-4 pb-4 border-b border-border-custom">
            <ClipboardList className="w-5 h-5 text-text-muted" />
            Historial de Órdenes
            </h3>
            <p className="text-text-muted text-sm">
            El historial de mantenciones de este vehículo se mostrará aquí una vez implementada la
            Gestión de Órdenes (próxima misión).
            </p>
        </div>
        </div>
    </div>
    );
}