import {
  Car,
  Clock,
  CheckCircle,
  FileText,
  TrendingUp,
  AlertTriangle,
} from 'lucide-react';

const stats = [
  {
    label: 'Vehículos en Taller',
    value: '—',
    valueColor: 'text-white',
    icon: <Car className="w-6 h-6" />,
    iconColor: 'text-blue-400',
    iconBg: 'bg-blue-400/15',
    borderLeft: 'border-l-4 border-l-primary-blue',
  },
  {
    label: 'Esperando Diagnóstico',
    value: '—',
    valueColor: 'text-status-yellow',
    icon: <Clock className="w-6 h-6" />,
    iconColor: 'text-status-yellow',
    iconBg: 'bg-status-yellow/15',
    borderLeft: 'border-l-4 border-l-status-orange',
  },
  {
    label: 'Listos para Entrega',
    value: '—',
    valueColor: 'text-status-green',
    icon: <CheckCircle className="w-6 h-6" />,
    iconColor: 'text-status-green',
    iconBg: 'bg-status-green/15',
    borderLeft: 'border-l-4 border-l-status-green',
  },
  {
    label: 'Presupuestos por Revisar',
    value: '—',
    valueColor: 'text-status-orange',
    icon: <FileText className="w-6 h-6" />,
    iconColor: 'text-status-orange',
    iconBg: 'bg-status-orange/15',
    borderLeft: 'border-l-4 border-l-status-red',
  },
];

export function AdminDashboardPage() {
  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center px-10 pt-10 pb-5">
        <div>
          <h2 className="text-3xl font-bold mb-2 tracking-tight">
            Panel de Control Global
          </h2>
          <p className="text-text-muted text-lg">
            Resumen operativo del taller
          </p>
        </div>
        <div className="bg-status-green/20 px-5 py-2.5 rounded-[20px] text-status-green text-sm font-bold border border-status-green/50">
          <span className="text-xs mr-2">●</span> Sistema En línea
        </div>
      </div>

      <div className="grid grid-cols-4 gap-5 px-10 pb-7">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className={`glass-card flex justify-between items-center p-5 ${stat.borderLeft}`}
          >
            <div>
              <span className="text-text-muted text-sm block mb-2">
                {stat.label}
              </span>
              <h3 className={`text-4xl font-extrabold ${stat.valueColor}`}>
                {stat.value}
              </h3>
            </div>
            <div
              className={`w-14 h-14 rounded-xl flex items-center justify-center text-2xl ${stat.iconColor} ${stat.iconBg}`}
            >
              {stat.icon}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[2fr_1fr] gap-7 px-10 pb-10">
        <div className="glass-card flex flex-col p-7">
          <div className="flex justify-between items-center mb-6 border-b border-border-custom pb-4">
            <h3 className="text-xl font-semibold">Cola de Trabajo Activa</h3>
          </div>
          <div className="flex flex-col gap-3.5">
            <p className="text-text-muted text-center py-10">
              Aún no hay órdenes de trabajo activas.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-7">
          <div className="glass-card">
            <div className="flex justify-between items-center mb-5 border-b border-border-custom pb-3">
              <h4 className="text-xl font-semibold">Actividad Reciente</h4>
            </div>
            <div className="flex flex-col gap-4">
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-status-green/10 flex items-center justify-center text-status-green shrink-0">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm mb-1">
                    <strong>Actividad pendiente</strong> de registro.
                  </p>
                  <p className="text-xs text-text-muted">
                    Pronto se mostrará el historial de operaciones.
                  </p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-status-yellow/10 flex items-center justify-center text-status-yellow shrink-0">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm mb-1">
                    <strong>Avisos</strong> visibles aquí.
                  </p>
                  <p className="text-xs text-text-muted">
                    Sin alertas por el momento.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
