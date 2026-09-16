import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { UserRole } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { FullScreenLoader } from '@/presentation/components/ui/FullScreenLoader';
import { getHomePath } from '@/presentation/routes/rolePaths';

interface ProtectedRouteProps {
  allowedRoles?: UserRole[];
  children: ReactNode;
}

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const { isInitializing, isAuthenticated, user } = useAuthStore();
  const location = useLocation();

  if (isInitializing) {
    return <FullScreenLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to={getHomePath(user.role)} replace />;
  }

  return <>{children}</>;
}