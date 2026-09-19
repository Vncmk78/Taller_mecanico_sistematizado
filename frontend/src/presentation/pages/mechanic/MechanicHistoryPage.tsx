import { History } from 'lucide-react';

export function MechanicHistoryPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Actividades</h2>
      <p className="text-text-muted text-lg mb-8">Historial de tu trabajo y tus registros</p>
      <div className="glass-card p-16 text-center">
        <History className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí verás tus intervenciones, fechas y observaciones registradas.
        </p>
      </div>
    </div>
  );
}