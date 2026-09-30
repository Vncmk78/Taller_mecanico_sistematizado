import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { UserRole } from '@/domain/entities/User';
import { useAuth } from '@/presentation/components/auth/authContext';
import { FullScreenLoader } from '@/presentation/components/ui/FullScreenLoader';

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

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <Navigate
        to="/acceso-denegado"
        state={{ message: `Tu rol (${user.role}) no tiene permisos para acceder a esta sección.` }}
        replace
      />
    );
  }

  return <>{children}</>;
}