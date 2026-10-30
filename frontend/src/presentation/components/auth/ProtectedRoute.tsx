import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { UserRole } from '@/domain/entities/User';
import { useAuth } from '@/presentation/components/auth/authContext';
import { FullScreenLoader } from '@/presentation/components/ui/FullScreenLoader';
import { getUserRoles } from '@/presentation/utils/roleVisibility';

interface ProtectedRouteProps {
  allowedRoles?: UserRole[];
  children: ReactNode;
}

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const { isInitializing, isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <FullScreenLoader />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const userRoles = getUserRoles(user);
    const tienePermiso = userRoles.some((role) => allowedRoles.includes(role));
    if (!tienePermiso) {
      const rolesTexto = userRoles.length > 0 ? userRoles.join(', ') : user.role || 'sin rol';
      return (
        <Navigate
          to="/acceso-denegado"
          state={{ message: `Tu rol (${rolesTexto}) no tiene permisos para acceder a esta sección.` }}
          replace
        />
      );
    }
  }

  return <>{children}</>;
}