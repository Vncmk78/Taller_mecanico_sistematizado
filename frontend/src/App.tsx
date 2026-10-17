import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '@/presentation/routes/AppRoutes';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { ErrorBoundary } from '@/presentation/components/ui/ErrorBoundary';
import { RouteChangeFocus } from '@/presentation/components/layout/RouteChangeFocus';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <AuthProvider>
            <ToastProvider>
              <RouteChangeFocus />
              <AppRoutes />
            </ToastProvider>
          </AuthProvider>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;