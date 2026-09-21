import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/presentation/components/auth/authContext';
import { getHomePath } from '@/presentation/routes/rolePaths';
import { FullScreenLoader } from '@/presentation/components/ui/FullScreenLoader';

interface PublicOnlyRouteProps {
  children: ReactNode;
}

export function PublicOnlyRoute({ children }: PublicOnlyRouteProps) {
  const { isInitializing, isAuthenticated, user } = useAuth();

  if (isInitializing) {
    return <FullScreenLoader />;
  }

  if (isAuthenticated) {
    return <Navigate to={user ? getHomePath(user.role) : '/'} replace />;
  }

  return <>{children}</>;
}