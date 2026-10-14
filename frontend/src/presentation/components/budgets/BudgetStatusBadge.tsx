import {
    estadoVersionLabel,
    type EstadoVersionPresupuesto,
} from '@/domain/entities/Presupuesto';

const statusStyles: Record<EstadoVersionPresupuesto, string> = {
    borrador: 'bg-bg-secondary text-text-muted border-border-custom',
    enviada: 'bg-status-orange/15 text-status-orange border-status-orange/40',
    aprobada: 'bg-status-green/15 text-status-green border-status-green/40',
    rechazada: 'bg-status-red/15 text-status-red border-status-red/40',
};

interface BudgetStatusBadgeProps {
    estado: EstadoVersionPresupuesto;
    className?: string;
}

/** Etiqueta visual del estado de la última versión del presupuesto. */
export function BudgetStatusBadge({ estado, className = '' }: BudgetStatusBadgeProps) {
    const label = estadoVersionLabel(estado);
    return (
        <span
            title={label}
            className={`inline-flex items-center rounded-full text-xs font-bold border px-2.5 py-1 whitespace-nowrap ${statusStyles[estado]} ${className}`}
        >
            {label}
        </span>
    );
}
