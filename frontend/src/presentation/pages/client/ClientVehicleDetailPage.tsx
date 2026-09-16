import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, CalendarPlus, ClipboardList } from 'lucide-react';
import { VehicleInfoPanel } from '@/presentation/components/vehicles/VehicleInfoPanel';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { CURRENT_CLIENT_ID } from '@/infrastructure/mocks/vehicles.mock';

export function ClientVehicleDetailPage() {
    const { id } = useParams<{ id: string }>();
    const user = useAuthStore((s) => s.user);
    const vehicles = useVehicleStore((s) => s.vehicles);
    const clientId = user?.id ?? CURRENT_CLIENT_ID;

    const vehicle = vehicles.find((v) => v.id === id && v.clientId === clientId);

    if (!vehicle) {
    return (
        <div className="text-text-muted">
        Vehículo no encontrado o no pertenece a su cuenta.{' '}
        <Link to="/client/vehiculos" className="text-primary-red">Volver a mis vehículos</Link>
        </div>
    );
    }

    return (
    <div className="animate-fade-in">
        <Link
        to="/client/vehiculos"
        className="inline-flex items-center gap-2 text-text-muted hover:text-white mb-6 no-underline"
        >
        <ArrowLeft className="w-4 h-4" /> Volver a mis vehículos
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-6">
        <div className="flex flex-col gap-4">
            <VehicleInfoPanel vehicle={vehicle} />
            <Link
            to="/client/agendar"
            className="bg-primary-red text-white py-3 rounded-lg font-bold text-center flex items-center justify-center gap-2 no-underline hover:bg-primary-red-hover transition-colors"
            >
            <CalendarPlus className="w-4 h-4" /> Agendar mantención para este vehículo
            </Link>
        </div>

        <div className="glass-card">
            <h3 className="text-xl font-semibold flex items-center gap-2 mb-4 pb-4 border-b border-border-custom">
            <ClipboardList className="w-5 h-5 text-text-muted" />
            Historial de Órdenes
            </h3>
            <p className="text-text-muted text-sm">
            Aquí verá el historial de mantenciones de este vehículo una vez implementada la Gestión
            de Órdenes (próxima misión).
            </p>
        </div>
        </div>
    </div>
    );
}