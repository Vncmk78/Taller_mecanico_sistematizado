import { ordenStatusLabel } from '@/domain/entities/Order';

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

interface OrderStatusBadgeProps {
    estadoCodigo: number;
}

export function OrderStatusBadge({ estadoCodigo }: OrderStatusBadgeProps) {
    return (
        <span
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold border whitespace-nowrap ${
                statusStyles[estadoCodigo] ?? 'bg-white/10 text-text-muted border-border-custom'
            }`}
        >
            {ordenStatusLabel(estadoCodigo)}
        </span>
    );
}