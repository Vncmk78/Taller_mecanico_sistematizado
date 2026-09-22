import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, ClipboardList, RefreshCw, History } from 'lucide-react';
import { useAuth } from '@/presentation/components/auth/authContext';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';

const sections = [
  {
    title: 'Portal Mecánico',
    items: [
      { to: '/mechanic', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Mi Panel', end: true },
      { to: '/mechanic/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Mis Órdenes' },
      { to: '/mechanic/estados', icon: <RefreshCw className="w-5 h-5" />, label: 'Actualizar Estados' },
      { to: '/mechanic/historial', icon: <History className="w-5 h-5" />, label: 'Actividades' },
    ],
  },
];

export function MechanicLayout() {
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
      badge="Portal Mecánico"
      userName={user?.full_name || user?.email || 'Mecánico'}
      userSubtitle="Mecánico"
      onLogout={handleLogout}
    />
  );
}