import { Link } from 'react-router-dom';
import { CalendarPlus, Car } from 'lucide-react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';

export function ClientDashboardPage() {
    const user = useAuthStore((s) => s.user);

    return (
    <div className="animate-fade-in text-center flex flex-col items-center justify-center min-h-[60vh] gap-8">
        <div>
        <h1 className="text-4xl font-bold mb-2">Bienvenido{user?.full_name ? `, ${user.full_name}` : ''}</h1>
        <p className="text-text-muted text-lg">Mantenga el control total sobre la salud de sus vehículos.</p>
        </div>
        <div className="flex w-full max-w-[600px] flex-col gap-6 sm:flex-row sm:justify-center">
        <Link
            to="/client/vehiculos"
            className="card w-full p-8 text-center no-underline text-text-main transition-transform hover:-translate-y-1 sm:w-[280px]"
        >
            <Car className="w-10 h-10 mx-auto mb-4 text-primary-blue" aria-hidden />
            <h3 className="font-semibold mb-1">Mis Vehículos</h3>
            <p className="text-text-muted text-sm">Consulte sus vehículos registrados</p>
        </Link>
        <Link
            to="/client/nuevas-atenciones"
            className="card w-full p-8 text-center no-underline text-text-main transition-transform hover:-translate-y-1 sm:w-[280px]"
        >
            <CalendarPlus className="w-10 h-10 mx-auto mb-4 text-status-green" aria-hidden />
            <h3 className="font-semibold mb-1">Nuevas Atenciones</h3>
            <p className="text-text-muted text-sm">Consulte sus solicitudes después de una cancelación</p>
        </Link>
        </div>
    </div>
    );
}