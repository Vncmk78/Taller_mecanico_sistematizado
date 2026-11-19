import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { GlassCard } from '@/presentation/components/ui/GlassCard';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  /**
   * Al cambiar de valor (p. ej. la ruta actual) se descarta el error capturado
   * y se vuelve a intentar el render, sin desmontar a los hijos sanos ni perder
   * el estado de los providers que están por encima.
   */
  resetKey?: string | number;
}

interface ErrorBoundaryState {
  hasError: boolean;
  /** Última `resetKey` vista, para detectar el cambio de ruta. */
  resetKey?: string | number;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): Partial<ErrorBoundaryState> {
    return { hasError: true };
  }

  static getDerivedStateFromProps(
    props: ErrorBoundaryProps,
    state: ErrorBoundaryState
  ): Partial<ErrorBoundaryState> | null {
    // Navegar a otra página debe dar otra oportunidad de render: sin esto, un
    // error de render dejaba la app inutilizable hasta recargar manualmente.
    // Se hace aquí (y no con setState en componentDidUpdate) para no encadenar
    // un segundo render tras cada actualización.
    if (props.resetKey !== state.resetKey) {
      return { resetKey: props.resetKey, hasError: false };
    }
    return null;
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Se registra solo el nombre, el mensaje y la pila de componentes: volcar
    // el objeto `error` completo imprimiría en la consola del navegador el
    // `config.headers.Authorization` de un AxiosError, es decir, el token de
    // acceso en claro. La consola es lo que se ve al compartir pantalla.
    console.error(
      'Error capturado por ErrorBoundary:',
      `${error?.name ?? 'Error'}: ${error?.message ?? 'sin mensaje'}`,
      errorInfo.componentStack,
    );
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
        <main
          id="contenido-principal"
          tabIndex={-1}
          className="min-h-screen flex flex-col items-center justify-center px-5 animate-fade-in focus:outline-none"
        >
          <GlassCard className="w-full max-w-[480px] p-6 sm:p-[40px_36px] text-center">
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
        </main>
      );
    }
    return this.props.children;
  }
}