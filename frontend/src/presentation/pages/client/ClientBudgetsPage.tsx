import { FileText } from 'lucide-react';

export function ClientBudgetsPage() {
  return (
    <div className="p-10 animate-fade-in">
      <h2 className="text-3xl font-bold mb-2 tracking-tight">Presupuestos</h2>
      <p className="text-text-muted text-lg mb-8">Consulta y decide sobre tus presupuestos</p>
      <div className="glass-card p-16 text-center">
        <FileText className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <p className="text-text-muted text-lg mb-2">Estructura en construcción</p>
        <p className="text-text-muted text-sm">
          Aquí podrás revisar, aprobar o rechazar tus presupuestos con evidencia.
        </p>
      </div>
    </div>
  );
}