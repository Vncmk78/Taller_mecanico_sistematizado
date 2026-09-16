import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Car, LayoutDashboard, LogOut, Settings, Wrench } from 'lucide-react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';

const navItems = [
    { to: '/mechanic', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Panel Principal', end: true },
    { to: '/mechanic/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Vehículos Asignados' },
];

export function MechanicLayout() {
    const navigate = useNavigate();
    const { user, logout } = useAuthStore();

    const handleLogout = () => {
    logout();
    navigate('/login');
    };

    return (
    <div className="flex min-h-screen">
        <aside className="w-[260px] bg-glass-sidebar border-r border-border-custom flex flex-col backdrop-blur-[20px] shrink-0">
        <div className="flex items-center gap-2.5 p-7 border-b border-border-custom">
            <span className="relative inline-block w-[35px] h-[35px] text-gray-400">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-red -rotate-15" />
            </span>
            <div className="text-sm leading-tight font-bold">
            Sistema<br />Mecánico
            </div>
        </div>
        <nav className="flex flex-col gap-2 p-5 flex-grow">
            <div className="text-xs text-gray-500 uppercase font-bold tracking-[1.5px] mx-4 mt-2 mb-2">
            Portal Mecánico
            </div>
            {navItems.map((item) => (
            <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                `flex items-center gap-3.5 px-4 py-3.5 rounded-[10px] transition-all duration-200 text-base no-underline ${
                    isActive
                    ? 'bg-primary-red text-white shadow-[0_4px_15px_rgba(211,47,47,0.3)] translate-x-[5px]'
                    : 'text-text-muted hover:bg-white/5 hover:text-white hover:translate-x-[5px]'
                }`
                }
            >
                {item.icon}
                {item.label}
            </NavLink>
            ))}
        </nav>
        </aside>
        <main className="flex-grow flex flex-col bg-glass-panel h-screen overflow-y-auto backdrop-blur-[8px]">
        <header className="flex justify-end items-center gap-4 px-10 py-4 border-b border-border-custom bg-black/30 backdrop-blur-[10px] sticky top-0 z-5">
            <span className="text-sm text-text-muted">{user?.email}</span>
            <button
            onClick={handleLogout}
            className="text-primary-red hover:text-white transition-colors bg-transparent border-none cursor-pointer"
            title="Cerrar sesión"
            >
            <LogOut className="w-5 h-5" />
            </button>
        </header>
        <div className="flex-grow">
            <Outlet />
        </div>
        </main>
    </div>
    );
}