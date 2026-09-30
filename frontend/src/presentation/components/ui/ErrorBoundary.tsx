import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { GlassCard } from '@/presentation/components/ui/GlassCard';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error capturado por ErrorBoundary:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="min-h-screen flex flex-col items-center justify-center px-5 animate-fade-in">
          <GlassCard className="w-full max-w-[480px] p-[40px_36px] text-center">
            <AlertTriangle className="w-14 h-14 mx-auto mb-5 text-status-red" />
            <h1 className="text-2xl font-bold tracking-tight text-text-main">
              Algo salió mal
            </h1>
            <p className="mt-3 text-text-muted text-base">
              Ocurrió un error inesperado al mostrar esta página. Recarga la página o
              inténtalo nuevamente.
            </p>
            <Button className="mt-8 w-full py-3" onClick={this.handleReload}>
              Recargar página
            </Button>
          </GlassCard>
        </div>
      );
    }
    return this.props.children;
  }
}