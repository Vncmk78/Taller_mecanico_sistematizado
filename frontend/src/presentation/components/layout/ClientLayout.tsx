import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  CalendarPlus,
  Car,
  ClipboardList,
  FileText,
  Settings,
  Wrench,
  LogOut,
} from 'lucide-react';
import { useAuth } from '@/presentation/components/auth/authContext';

const navItems = [
  { to: '/client', label: 'Mi Portal', icon: <LayoutDashboard className="w-5 h-5" />, end: true },
  { to: '/client/vehiculos', label: 'Mis Vehículos', icon: <Car className="w-5 h-5" /> },
  { to: '/client/agendar', label: 'Agendar Mantención', icon: <CalendarPlus className="w-5 h-5" /> },
  { to: '/client/servicios', label: 'Estado del Servicio', icon: <ClipboardList className="w-5 h-5" /> },
  { to: '/client/presupuestos', label: 'Presupuestos', icon: <FileText className="w-5 h-5" /> },
];

export function ClientLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex flex-col animate-fade-in">
      <header className="flex items-center justify-between px-10 py-4 border-b border-border-custom bg-black/80 backdrop-blur-[10px] sticky top-0 z-50">
        <div className="flex items-center gap-2.5">
          <span className="relative inline-block w-[35px] h-[35px] text-gray-400">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-red -rotate-15" />
          </span>
          <div className="text-sm leading-tight font-bold">
            Sistema<br />Mecánico
          </div>
          <span className="ml-3 text-xs bg-primary-red/15 text-primary-red px-3 py-1 rounded-full border border-primary-red/40 font-bold">
            Portal Cliente
          </span>
        </div>

        <nav className="flex gap-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-4 py-2.5 rounded-[10px] transition-all duration-200 text-sm font-medium no-underline ${
                  isActive
                    ? 'bg-primary-red text-white shadow-[0_4px_15px_rgba(211,47,47,0.3)]'
                    : 'text-text-muted hover:bg-white/5 hover:text-white'
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-sm font-bold">{user?.full_name || user?.email || 'Cliente'}</div>
            <div className="text-xs text-text-muted">Cliente</div>
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

      <main className="flex-grow">
        <Outlet />
      </main>
    </div>
  );
}