import { LayoutDashboard } from 'lucide-react';

export function ClientPortalPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Mi Portal</h2>
      <p className="text-text-muted text-lg mb-8">Resumen de tus servicios en el taller</p>
      <div className="glass-card p-16 text-center">
        <LayoutDashboard className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí verás el resumen de tus vehículos, servicios en curso y notificaciones.
        </p>
      </div>
    </div>
  );
}