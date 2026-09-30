import { ordenStatusLabel } from '@/domain/entities/Order';
import { estadoDotClasses } from '@/presentation/utils/orderDisplay';

const statusStyles: Record<number, string> = {
    1: 'bg-status-blue/15 text-status-blue border-status-blue/40',
    2: 'bg-status-yellow/15 text-status-yellow border-status-yellow/40',
    3: 'bg-status-purple/15 text-status-purple border-status-purple/40',
    4: 'bg-status-orange/15 text-status-orange border-status-orange/40',
    5: 'bg-status-yellow/15 text-status-yellow border-status-yellow/40',
    6: 'bg-status-green/15 text-status-green border-status-green/40',
    7: 'bg-status-green/15 text-status-green border-status-green/40',
    8: 'bg-status-red/15 text-status-red border-status-red/40',
};

export type OrderStatusBadgeVariant = 'pill' | 'dot';
export type OrderStatusBadgeSize = 'sm' | 'md';

interface OrderStatusBadgeProps {
    estadoCodigo: number;
    /** `pill` (por defecto): etiqueta con fondo tintado y borde. `dot`: punto de color + etiqueta, compacto. */
    variant?: OrderStatusBadgeVariant;
    size?: OrderStatusBadgeSize;
    className?: string;
}

// Pill: mantiene el estilo visual histórico. Dot: compacto, sin fondo ni borde.
const variantSizeClasses: Record<OrderStatusBadgeVariant, Record<OrderStatusBadgeSize, string>> = {
    pill: {
        md: 'text-xs px-2.5 py-1',
        sm: 'text-[11px] px-2 py-0.5',
    },
    dot: {
        md: 'text-sm gap-1.5',
        sm: 'text-xs gap-1',
    },
};

/**
 * Etiqueta visual del estado de una orden (catálogo fijo 1-8). Expone dos
 * variantes: `pill` (tarjeta, panel de detalle) y `dot` (punto + etiqueta,
 * listas/timelines compactos), ambas con tamaño `sm`/`md` y tooltip con la
 * etiqueta completa del estado.
 */
export function OrderStatusBadge({
    estadoCodigo,
    variant = 'pill',
    size = 'md',
    className = '',
}: OrderStatusBadgeProps) {
    const label = ordenStatusLabel(estadoCodigo);
    const sizing = variantSizeClasses[variant][size];

    if (variant === 'dot') {
        return (
            <span
                title={label}
                className={`inline-flex items-center font-medium whitespace-nowrap ${sizing} ${className}`}
            >
                <span
                    aria-hidden
                    className={`h-2 w-2 rounded-full ${estadoDotClasses[estadoCodigo] ?? 'bg-bg-secondary'}`}
                />
                {label}
            </span>
        );
    }

    return (
        <span
            title={label}
            className={`inline-flex items-center rounded-full font-bold border whitespace-nowrap ${sizing} ${
                statusStyles[estadoCodigo] ?? 'bg-bg-secondary text-text-muted border-border-custom'
            } ${className}`}
        >
            {label}
        </span>
    );
}