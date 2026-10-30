import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, ClipboardList, RefreshCw, Car } from 'lucide-react';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';
import { useRoleAccess } from '@/presentation/hooks/useRoleAccess';

const sections = [
  {
    title: 'Portal Mecánico',
    items: [
      { to: '/mechanic', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Mi Panel', end: true, roles: ['mecanico' as const] },
      { to: '/mechanic/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Mis Órdenes', roles: ['mecanico' as const] },
      { to: '/mechanic/estados', icon: <RefreshCw className="w-5 h-5" />, label: 'Actualizar Estados', roles: ['mecanico' as const] },
      { to: '/mechanic/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Vehículos Asignados', roles: ['mecanico' as const] },
    ],
  },
];

export function MechanicLayout() {
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
      badge="Portal Mecánico"
      userName={user?.full_name || user?.email || 'Mecánico'}
      userSubtitle="Mecánico"
      onLogout={handleLogout}
    />
  );
}