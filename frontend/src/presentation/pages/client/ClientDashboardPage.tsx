import { Link } from 'react-router-dom';
import { CalendarPlus, Car } from 'lucide-react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';

export function ClientDashboardPage() {
    const user = useAuthStore((s) => s.user);

    return (
    <div className="animate-fade-in text-center flex flex-col items-center justify-center min-h-[60vh] gap-8">
        <div>
        <h2 className="text-4xl font-bold mb-2">Bienvenido{user?.full_name ? `, ${user.full_name}` : ''}</h2>
        <p className="text-text-muted text-lg">Mantenga el control total sobre la salud de sus vehículos.</p>
        </div>
        <div className="flex gap-6">
        <Link
            to="/client/vehiculos"
            className="glass-card w-[280px] p-8 text-center no-underline text-white hover:-translate-y-1 transition-transform"
        >
            <Car className="w-10 h-10 mx-auto mb-4 text-primary-blue" />
            <h3 className="font-semibold mb-1">Mis Vehículos</h3>
            <p className="text-text-muted text-sm">Consulte sus vehículos registrados</p>
        </Link>
        <Link
            to="/client/agendar"
            className="glass-card w-[280px] p-8 text-center no-underline text-white hover:-translate-y-1 transition-transform"
        >
            <CalendarPlus className="w-10 h-10 mx-auto mb-4 text-status-green" />
            <h3 className="font-semibold mb-1">Agendar Mantención</h3>
            <p className="text-text-muted text-sm">Solicite una nueva hora de atención</p>
        </Link>
        </div>
    </div>
    );
}