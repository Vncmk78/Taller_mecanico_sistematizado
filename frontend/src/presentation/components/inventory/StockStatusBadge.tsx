import { getStockStatus } from '@/presentation/utils/stockStatus';
import type { Repuesto } from '@/domain/entities/Repuesto';

interface StockStatusBadgeProps {
    repuesto: Repuesto;
    className?: string;
}

export function StockStatusBadge({ repuesto, className = '' }: StockStatusBadgeProps) {
    const status = getStockStatus(repuesto);

    return (
        <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.className} ${className}`}
            aria-label={`Estado de stock: ${status.label}`}
            title={`Estado de stock: ${status.label}`}
        >
            {status.label}
        </span>
    );
}
