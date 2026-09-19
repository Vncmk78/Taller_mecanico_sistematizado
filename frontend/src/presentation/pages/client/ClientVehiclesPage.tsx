import { Car } from 'lucide-react';

export function ClientVehiclesPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Mis Vehículos</h2>
      <p className="text-text-muted text-lg mb-8">Consulta los vehículos registrados a tu nombre</p>
      <div className="glass-card p-16 text-center">
        <Car className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí podrás ver el listado, el detalle y el historial de tus vehículos.
        </p>
      </div>
    </div>
  );
}