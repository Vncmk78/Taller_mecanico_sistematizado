import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardList,
  Users,
  Car,
  Package,
  Truck,
  Search,
  Bell,
} from 'lucide-react';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';
import { useRoleAccess } from '@/presentation/hooks/useRoleAccess';

const sections = [
  {
    title: 'Portal Administrador',
    items: [
      { to: '/admin', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Panel de Control', end: true, roles: ['administrador' as const] },
      { to: '/admin/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Gestión de Órdenes', roles: ['administrador' as const] },
      { to: '/admin/clientes', icon: <Users className="w-5 h-5" />, label: 'Clientes', roles: ['administrador' as const] },
    ],
  },
  {
    title: 'Catálogo',
    items: [
      { to: '/admin/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Vehículos', roles: ['administrador' as const] },
      { to: '/admin/inventario', icon: <Package className="w-5 h-5" />, label: 'Inventario', roles: ['administrador' as const] },
      { to: '/admin/distribuidores', icon: <Truck className="w-5 h-5" />, label: 'Distribuidores', roles: ['administrador' as const] },
    ],
  },
];

export function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout, canShow } = useRoleAccess();

  const filteredSections = sections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => (item.roles ? canShow(item.roles) : true)),
    }))
    .filter((section) => section.items.length > 0);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <RoleLayout
      variant="sidebar"
      sections={filteredSections}
      userName={user?.email || 'admin@taller.cl'}
      userSubtitle="Administrador"
      onLogout={handleLogout}
      headerLeft={
        <div role="search" aria-label="Búsqueda global" className="flex items-center gap-3">
          <Search className="text-text-muted w-5 h-5" aria-hidden />
          <input
            type="search"
            name="busqueda-global"
            placeholder="Buscar patente, orden o cliente..."
            aria-label="Buscar patente, orden o cliente"
            autoComplete="off"
            className="py-2.5 px-4 bg-bg-secondary border-none rounded-lg text-text-main text-sm outline-none w-[350px] placeholder:text-text-muted"
          />
        </div>
      }
      headerRightPrepend={
        <button
          type="button"
          aria-label="Notificaciones"
          className="text-text-muted hover:text-primary-blue transition-colors cursor-pointer bg-transparent border-none p-1"
        >
          <Bell className="w-5 h-5" />
        </button>
      }
    />
  );
}