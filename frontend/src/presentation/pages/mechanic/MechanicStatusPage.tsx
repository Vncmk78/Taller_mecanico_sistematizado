import { RefreshCw } from 'lucide-react';

export function MechanicStatusPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Actualizar Estados</h2>
      <p className="text-text-muted text-lg mb-8">Mantén el flujo de las órdenes al día</p>
      <div className="glass-card p-16 text-center">
        <RefreshCw className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí podrás registrar el avance de cada orden y su historial de estados.
        </p>
      </div>
    </div>
  );
}