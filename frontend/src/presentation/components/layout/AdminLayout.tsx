import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Settings,
  Wrench,
  LayoutDashboard,
  ClipboardList,
  Users,
  Car,
  Package,
  Truck,
  LogOut,
  Search,
  Bell,
} from 'lucide-react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';

const navItems = [
  { to: '/admin', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Panel de Control', end: true },
  { to: '/admin/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Gestión de Órdenes' },
  { to: '/admin/clientes', icon: <Users className="w-5 h-5" />, label: 'Clientes' },
];

const catalogItems = [
  { to: '/admin/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Vehículos' },
  { to: '/admin/inventario', icon: <Package className="w-5 h-5" />, label: 'Inventario' },
  { to: '/admin/distribuidores', icon: <Truck className="w-5 h-5" />, label: 'Distribuidores' },
];

export function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

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
            Portal Administrador
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

          <div className="text-xs text-gray-500 uppercase font-bold tracking-[1.5px] mx-4 mt-5 mb-2">
            Catálogo
          </div>
          {catalogItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
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
          <div className="flex items-center gap-3">
            <Search className="text-text-muted w-5 h-5" />
            <input
              type="text"
              placeholder="Buscar patente, orden o cliente..."
              className="py-2.5 px-4 bg-black/40 border-none rounded-lg text-white text-sm outline-none w-[350px] placeholder:text-text-muted"
            />
          </div>
          <div className="flex items-center gap-3">
            <Bell className="text-text-muted cursor-pointer w-5 h-5" />
            <div className="text-right ml-4">
              <div className="text-sm font-bold">{user?.email || 'admin@taller.cl'}</div>
              <div className="text-xs text-text-muted">Administrador</div>
            </div>
            <button
              onClick={handleLogout}
              className="ml-5 text-primary-red cursor-pointer text-lg bg-transparent border-none hover:text-white transition-colors"
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
