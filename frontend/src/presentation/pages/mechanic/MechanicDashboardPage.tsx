import { Link } from 'react-router-dom';
import { Car } from 'lucide-react';

export function MechanicDashboardPage() {
    return (
    <div className="animate-fade-in p-10">
        <h2 className="text-3xl font-bold mb-2">Panel del Mecánico</h2>
        <p className="text-text-muted mb-6">
        La Gestión de Órdenes se implementará en una próxima misión. Por ahora puede revisar los
        vehículos de sus órdenes asignadas.
        </p>
        <Link
        to="/mechanic/vehiculos"
        className="inline-flex items-center gap-2 bg-primary-red text-white px-5 py-3 rounded-lg font-bold no-underline"
        >
        <Car className="w-4 h-4" /> Ver vehículos asignados
        </Link>
    </div>
    );
}