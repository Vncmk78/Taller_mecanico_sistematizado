import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, Car, CalendarPlus, ClipboardList, FileText } from 'lucide-react';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';
import { useRoleAccess } from '@/presentation/hooks/useRoleAccess';

const sections = [
  {
    items: [
      { to: '/client', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Mi Portal', end: true, roles: ['cliente' as const] },
      { to: '/client/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Mis Vehículos', roles: ['cliente' as const] },
      { to: '/client/agendar', icon: <CalendarPlus className="w-5 h-5" />, label: 'Agendar Mantención', roles: ['cliente' as const] },
      { to: '/client/servicios', icon: <ClipboardList className="w-5 h-5" />, label: 'Estado del Servicio', roles: ['cliente' as const] },
      { to: '/client/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Mis Órdenes', roles: ['cliente' as const] },
      { to: '/client/presupuestos', icon: <FileText className="w-5 h-5" />, label: 'Presupuestos', roles: ['cliente' as const] },
    ],
  },
];

export function ClientLayout() {
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
      variant="topnav"
      sections={filteredSections}
      badge="Portal Cliente"
      userName={user?.full_name || user?.email || 'Cliente'}
      userSubtitle="Cliente"
      onLogout={handleLogout}
    />
  );
}