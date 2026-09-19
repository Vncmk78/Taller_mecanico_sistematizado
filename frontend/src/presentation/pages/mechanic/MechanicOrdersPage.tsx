import { ClipboardList } from 'lucide-react';

export function MechanicOrdersPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Mis Órdenes</h2>
      <p className="text-text-muted text-lg mb-8">Órdenes de trabajo asignadas a tu cuenta</p>
      <div className="glass-card p-16 text-center">
        <ClipboardList className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí podrás ver el listado, el detalle y las órdenes pendientes de tu carga.
        </p>
      </div>
    </div>
  );
}