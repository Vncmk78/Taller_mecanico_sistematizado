import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { ErrorBoundary } from '@/presentation/components/ui/ErrorBoundary';

interface RouteErrorBoundaryProps {
  children: ReactNode;
  /** Fallback opcional; por defecto se usa la pantalla de error del ErrorBoundary. */
  fallback?: ReactNode;
}

/**
 * ErrorBoundary consciente de la navegación: descarta el error capturado
 * cuando la ruta cambia (resetKey = pathname), de modo que un error de render
 * en una página no deje la app inutilizable hasta que el usuario recargue.
 *
 * Se monta alrededor de AppRoutes, por dentro de los providers (Toast, Auth):
 * así el error de una página no arrastra la sesión ni las notificaciones, y
 * al navegar se recupera sin recargar.
 */
export function RouteErrorBoundary({ children, fallback }: RouteErrorBoundaryProps) {
  const location = useLocation();
  return (
    <ErrorBoundary resetKey={location.pathname} fallback={fallback}>
      {children}
    </ErrorBoundary>
  );
}
