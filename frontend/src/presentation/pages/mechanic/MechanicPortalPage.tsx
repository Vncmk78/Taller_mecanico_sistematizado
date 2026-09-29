import { LayoutDashboard } from 'lucide-react';

export function MechanicPortalPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Mi Panel</h2>
      <p className="text-text-muted text-lg mb-8">Resumen de tu trabajo y órdenes asignadas</p>
      <div className="glass-card p-16 text-center">
        <LayoutDashboard className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí verás tus órdenes activas, carga de trabajo e indicadores personales.
        </p>
      </div>
    </div>
  );
}