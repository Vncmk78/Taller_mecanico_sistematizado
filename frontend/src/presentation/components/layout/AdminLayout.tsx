import { useNavigate } from 'react-router-dom';
import {
  Bell,
  LayoutDashboard,
  ClipboardList,
  Users,
  Car,
  Package,
  Truck,
  Search,
  AlertTriangle,
  ListOrdered,
  Gauge,
  SlidersHorizontal,
  RotateCcw,
  ClipboardX,
  UserCog,
} from 'lucide-react';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';
import { useRoleAccess } from '@/presentation/hooks/useRoleAccess';

const sections = [
  {
    title: 'Portal Administrador',
    items: [
      { to: '/admin', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Panel de Control', end: true, roles: ['administrador' as const] },
      { to: '/admin/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Gestión de Órdenes', roles: ['administrador' as const] },
      { to: '/admin/nuevas-atenciones', icon: <RotateCcw className="w-5 h-5" />, label: 'Nuevas atenciones', roles: ['administrador' as const] },
      { to: '/admin/cancelaciones', icon: <ClipboardX className="w-5 h-5" />, label: 'Cancelaciones pendientes', roles: ['administrador' as const] },
      { to: '/admin/clientes', icon: <Users className="w-5 h-5" />, label: 'Clientes', roles: ['administrador' as const] },
      { to: '/admin/usuarios', icon: <UserCog className="w-5 h-5" />, label: 'Usuarios y roles', roles: ['administrador' as const] },
      { to: '/admin/configuracion', icon: <SlidersHorizontal className="w-5 h-5" />, label: 'Capacidad del taller', roles: ['administrador' as const] },
      { to: '/admin/notificaciones', icon: <Bell className="w-5 h-5" />, label: 'Centro de avisos', roles: ['administrador' as const] },
    ],
  },
  {
    title: 'Catálogo',
    items: [
      { to: '/admin/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Vehículos', roles: ['administrador' as const] },
      { to: '/admin/inventario', icon: <Package className="w-5 h-5" />, label: 'Inventario', roles: ['administrador' as const] },
      { to: '/admin/inventario/alertas', icon: <AlertTriangle className="w-5 h-5" />, label: 'Alertas de stock', roles: ['administrador' as const] },
      { to: '/admin/inventario/movimientos', icon: <ListOrdered className="w-5 h-5" />, label: 'Movimientos', roles: ['administrador' as const] },
      { to: '/admin/inventario/umbral', icon: <Gauge className="w-5 h-5" />, label: 'Umbral general', roles: ['administrador' as const] },
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
        <div role="search" aria-label="Búsqueda global" className="hidden min-w-0 items-center gap-3 md:flex">
          <Search className="text-text-muted w-5 h-5 shrink-0" aria-hidden />
          <input
            type="search"
            name="busqueda-global"
            placeholder="Buscar patente, orden o cliente..."
            aria-label="Buscar patente, orden o cliente"
            autoComplete="off"
            className="py-2.5 px-4 bg-bg-secondary border-none rounded-lg text-text-main text-sm outline-none w-[220px] lg:w-[350px] placeholder:text-text-muted"
          />
        </div>
      }
    />
  );
}
