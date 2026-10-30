import { Link } from 'react-router-dom';
import { CalendarClock, Eye, FileCheck2, Wrench } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import { BudgetStatusBadge } from '@/presentation/components/budgets/BudgetStatusBadge';
import { formatDate } from '@/presentation/utils/orderDisplay';
import { formatMoneyCLP } from '@/presentation/utils/budgetDisplay';

interface BudgetCardProps {
    order: Order;
    presupuesto: Presupuesto;
    patente?: string;
    vehicleLabel?: string;
}

/** Tarjeta del listado "Mis Presupuestos": orden, estado, total y acción. */
export function BudgetCard({ order, presupuesto, patente, vehicleLabel }: BudgetCardProps) {
    const pendiente = presupuesto.estadoUltimaVersion === 'enviada';

    return (
        <div
            className={`card p-5 flex flex-col gap-3 overflow-hidden ${
                pendiente ? 'border-status-orange/70 shadow-[0_0_18px_rgba(242,106,46,0.15)]' : ''
            }`}
        >
            <div className="flex justify-between items-center gap-3">
                <h3 className="text-lg font-semibold flex items-center gap-2 min-w-0">
                    <Wrench className="w-5 h-5 text-text-muted shrink-0" aria-hidden />
                    <span className="truncate">Servicio n° {order.id}</span>
                </h3>
                <BudgetStatusBadge estado={presupuesto.estadoUltimaVersion} className="shrink-0" />
            </div>

            <div className="flex items-center gap-2">
                {patente && (
                    <span className="bg-bg-secondary text-text-main font-mono font-bold text-sm px-2.5 py-0.5 rounded tracking-wide shrink-0">
                        {patente}
                    </span>
                )}
                <span className="text-text-main text-sm truncate">
                    {vehicleLabel ?? `Vehículo N°${order.vehicleId}`}
                </span>
            </div>

            <div className="flex items-center gap-2 text-sm text-text-muted">
                <CalendarClock className="w-4 h-4 shrink-0" aria-hidden />
                Versión {presupuesto.ultimaVersion} · {formatDate(presupuesto.creadoEn)}
            </div>

            <div className="flex justify-between items-center mt-1">
                <span className="text-text-muted">Total:</span>
                <span className="text-2xl font-bold">{formatMoneyCLP(presupuesto.totalUltimaVersion)}</span>
            </div>

            {pendiente && (
                <p className="text-sm font-semibold text-status-orange bg-status-orange/10 border border-status-orange/30 rounded-lg px-3 py-2">
                    Requiere su aprobación o rechazo
                </p>
            )}

            <Link
                to={`/client/presupuestos/${order.id}`}
                className={`mt-auto flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-bold no-underline transition-colors ${
                    pendiente
                        ? 'bg-primary-blue text-white hover:bg-primary-blue-hover'
                        : 'bg-surface border border-border-custom text-primary-blue hover:bg-bg-secondary'
                }`}
            >
                {pendiente ? <FileCheck2 className="w-4 h-4" aria-hidden /> : <Eye className="w-4 h-4" aria-hidden />}
                {pendiente ? 'Revisar y Aprobar' : 'Ver detalle'}
            </Link>
        </div>
    );
}
