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
import { useAuth } from '@/presentation/components/auth/authContext';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';

const sections = [
  {
    title: 'Portal Administrador',
    items: [
      { to: '/admin', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Panel de Control', end: true },
      { to: '/admin/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Gestión de Órdenes' },
      { to: '/admin/clientes', icon: <Users className="w-5 h-5" />, label: 'Clientes' },
    ],
  },
  {
    title: 'Catálogo',
    items: [
      { to: '/admin/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Vehículos' },
      { to: '/admin/inventario', icon: <Package className="w-5 h-5" />, label: 'Inventario' },
      { to: '/admin/distribuidores', icon: <Truck className="w-5 h-5" />, label: 'Distribuidores' },
    ],
  },
];

export function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <RoleLayout
      variant="sidebar"
      sections={sections}
      userName={user?.email || 'admin@taller.cl'}
      userSubtitle="Administrador"
      onLogout={handleLogout}
      headerLeft={
        <div className="flex items-center gap-3">
          <Search className="text-text-muted w-5 h-5" />
          <input
            type="text"
            placeholder="Buscar patente, orden o cliente..."
            className="py-2.5 px-4 bg-black/40 border-none rounded-lg text-white text-sm outline-none w-[350px] placeholder:text-text-muted"
          />
        </div>
      }
      headerRightPrepend={<Bell className="text-text-muted cursor-pointer w-5 h-5" />}
    />
  );
}