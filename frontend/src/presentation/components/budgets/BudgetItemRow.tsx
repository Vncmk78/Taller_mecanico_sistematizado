import { Package, Wrench } from 'lucide-react';
import type { ItemPresupuesto } from '@/domain/entities/Presupuesto';
import { formatMoneyCLP } from '@/presentation/utils/budgetDisplay';

interface BudgetItemRowProps {
    item: ItemPresupuesto;
}

/** Fila de un ítem del presupuesto: repuesto (con su procedencia) o mano de obra. */
export function BudgetItemRow({ item }: BudgetItemRowProps) {
    const esRepuesto = item.tipo === 'repuesto';
    const Icon = esRepuesto ? Package : Wrench;
    const procedencia = item.repuestoNombre ?? item.descripcion;

    return (
        <div className="flex items-center justify-between gap-4 bg-bg-secondary rounded-lg px-4 py-3">
            <div className="flex items-center gap-3 min-w-0">
                <span className="flex items-center justify-center w-9 h-9 rounded-lg bg-surface text-primary-blue shrink-0">
                    <Icon className="w-4 h-4" aria-hidden />
                </span>
                <div className="min-w-0">
                    <p className="font-semibold text-text-main truncate">{procedencia}</p>
                    {esRepuesto && item.proveedorNombre && (
                        <p className="text-xs text-status-blue truncate">
                            Origen: {item.proveedorNombre}
                        </p>
                    )}
                    <p className="text-xs text-text-muted">
                        {item.cantidad} × {formatMoneyCLP(item.precioUnitario)}
                    </p>
                </div>
            </div>
            <span className="font-bold whitespace-nowrap">{formatMoneyCLP(item.subtotal)}</span>
        </div>
    );
}
