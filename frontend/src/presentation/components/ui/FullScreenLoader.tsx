import { Spinner } from '@/presentation/components/ui/Spinner';

interface FullScreenLoaderProps {
  message?: string;
}

export function FullScreenLoader({ message = 'Verificando sesión...' }: FullScreenLoaderProps = {}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 animate-fade-in">
      <Spinner className="w-12 h-12 text-primary-blue" label={message} />
      <p className="text-text-muted text-sm">{message}</p>
    </div>
  );
}