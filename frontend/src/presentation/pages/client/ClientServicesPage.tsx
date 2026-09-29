import { ClipboardList } from 'lucide-react';

export function ClientServicesPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Estado del Servicio</h2>
      <p className="text-text-muted text-lg mb-8">Seguimiento en tiempo real del estado de tus órdenes</p>
      <div className="glass-card p-16 text-center">
        <ClipboardList className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí podrás seguir el estado, el historial y la evidencia del servicio.
        </p>
      </div>
    </div>
  );
}