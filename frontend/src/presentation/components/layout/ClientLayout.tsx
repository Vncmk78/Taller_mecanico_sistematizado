import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, Car, CalendarPlus, ClipboardList, FileText } from 'lucide-react';
import { useAuth } from '@/presentation/components/auth/authContext';
import { RoleLayout } from '@/presentation/components/layout/RoleLayout';

const sections = [
  {
    items: [
      { to: '/client', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Mi Portal', end: true },
      { to: '/client/vehiculos', icon: <Car className="w-5 h-5" />, label: 'Mis Vehículos' },
      { to: '/client/agendar', icon: <CalendarPlus className="w-5 h-5" />, label: 'Agendar Mantención' },
      { to: '/client/servicios', icon: <ClipboardList className="w-5 h-5" />, label: 'Estado del Servicio' },
      { to: '/client/ordenes', icon: <ClipboardList className="w-5 h-5" />, label: 'Mis Órdenes' },
      { to: '/client/presupuestos', icon: <FileText className="w-5 h-5" />, label: 'Presupuestos' },
    ],
  },
];

export function ClientLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <RoleLayout
      variant="topnav"
      sections={sections}
      badge="Portal Cliente"
      userName={user?.full_name || user?.email || 'Cliente'}
      userSubtitle="Cliente"
      onLogout={handleLogout}
    />
  );
}