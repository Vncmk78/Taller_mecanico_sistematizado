import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Car,
  ClipboardList,
  RefreshCw,
  History,
  Settings,
  Wrench,
  LogOut,
} from 'lucide-react';
import { useAuth } from '@/presentation/components/auth/authContext';

const navItems = [
  { to: '/mechanic', label: 'Mi Panel', icon: <LayoutDashboard className="w-5 h-5" />, end: true },
  { to: '/mechanic/ordenes', label: 'Mis Órdenes', icon: <ClipboardList className="w-5 h-5" /> },
  { to: '/mechanic/estados', label: 'Actualizar Estados', icon: <RefreshCw className="w-5 h-5" /> },
  { to: '/mechanic/historial', label: 'Actividades', icon: <History className="w-5 h-5" /> },
  { to: '/mechanic/vehiculos', label: 'Vehículos Asignados', icon: <Car className="w-5 h-5" /> },
];

export function MechanicLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen">
      <aside className="w-[280px] bg-glass-sidebar border-r border-border-custom flex flex-col backdrop-blur-[20px] z-10 shrink-0">
        <div className="flex items-center gap-2.5 p-7 border-b border-border-custom">
          <span className="relative inline-block w-[35px] h-[35px] text-gray-400">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-red -rotate-15" />
          </span>
          <div className="text-sm leading-tight font-bold">
            Sistema<br />Mecánico
          </div>
        </div>

        <nav className="flex flex-col gap-2 p-5 flex-grow overflow-y-auto">
          <div className="text-xs text-gray-500 uppercase font-bold tracking-[1.5px] mx-4 mt-4 mb-2">
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
        <header className="flex justify-between items-center px-10 py-4 border-b border-border-custom bg-black/30 backdrop-blur-[10px] sticky top-0 z-5">
          <div className="text-xs bg-status-blue/15 text-status-blue px-3 py-1 rounded-full border border-status-blue/40 font-bold">
            Portal Mecánico
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm font-bold">{user?.full_name || user?.email || 'Mecánico'}</div>
              <div className="text-xs text-text-muted">Mecánico</div>
            </div>
            <button
              onClick={handleLogout}
              className="text-primary-red cursor-pointer text-lg bg-transparent border-none hover:text-white transition-colors"
              title="Cerrar Sesión"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </header>

        <div className="flex-grow">
          <Outlet />
        </div>
      </main>
    </div>
  );
}