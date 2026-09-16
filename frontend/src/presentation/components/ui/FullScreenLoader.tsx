import { Loader2 } from 'lucide-react';

export function FullScreenLoader() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 animate-fade-in">
      <Loader2 className="w-12 h-12 text-primary-red animate-spin" />
      <p className="text-text-muted text-sm">Verificando sesión...</p>
    </div>
  );
}