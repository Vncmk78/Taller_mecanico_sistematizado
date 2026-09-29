import { Truck } from 'lucide-react';

export function AdminDistributorsPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Distribuidores</h2>
      <p className="text-text-muted text-lg mb-8">Administración de proveedores y distribuidores</p>
      <div className="glass-card p-16 text-center">
        <Truck className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí se administrarán los distribuidores y proveedores de repuestos.
        </p>
      </div>
    </div>
  );
}