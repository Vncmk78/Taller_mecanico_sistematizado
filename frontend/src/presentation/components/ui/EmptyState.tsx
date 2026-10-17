import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
    title: string;
    description?: string;
    icon?: LucideIcon;
    /** Acción opcional (limpiar filtros, crear recurso, etc.). */
    action?: ReactNode;
    className?: string;
}

/**
 * Estado vacío reutilizable: explica que no hay datos y, si corresponde, ofrece
 * una acción para salir de esa situación. Pensado para renderizarse dentro del
 * grid de un listado (col-span-full) o suelto en una página de detalle.
 */
export function EmptyState({
    title,
    description,
    icon: Icon = Inbox,
    action,
    className = '',
}: EmptyStateProps) {
    return (
        <div
            className={`col-span-full flex flex-col items-center justify-center text-center py-12 px-6 ${className}`}
        >
            <span className="flex items-center justify-center w-14 h-14 rounded-full bg-bg-secondary text-text-muted mb-4">
                <Icon className="w-6 h-6" aria-hidden="true" />
            </span>
            <p className="text-text-muted font-medium">{title}</p>
            {description && <p className="text-text-muted text-sm mt-1 max-w-md">{description}</p>}
            {action && <div className="mt-4">{action}</div>}
        </div>
    );
}
