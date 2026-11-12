import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '@/presentation/routes/AppRoutes';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { ErrorBoundary } from '@/presentation/components/ui/ErrorBoundary';
import { RouteErrorBoundary } from '@/presentation/components/ui/RouteErrorBoundary';
import { RouteChangeFocus } from '@/presentation/components/layout/RouteChangeFocus';
import { createQueryClient } from '@/infrastructure/api/queryClient';

const queryClient = createQueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <AuthProvider>
            <ToastProvider>
              <RouteChangeFocus />
              {/* Capa externa: errores de los providers (sin recuperación por
                  navegación). Capa interna: errores de página, que se descartan
                  al cambiar de ruta sin recargar la app. */}
              <RouteErrorBoundary>
                <AppRoutes />
              </RouteErrorBoundary>
            </ToastProvider>
          </AuthProvider>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;