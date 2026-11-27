import { Link } from 'react-router-dom';
import { ClipboardList, FileText, User } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { formatDate } from '@/presentation/utils/orderDisplay';

interface OrderCardProps {
    order: Order;
    detailPath: string;
    patente?: string;
    vehicleLabel?: string;
    mechanicName?: string;
}

export function OrderCard({ order, detailPath, patente, vehicleLabel, mechanicName }: OrderCardProps) {
    return (
        <div className="card p-0 overflow-hidden flex flex-col">
            <div className="p-5 flex-grow flex flex-col">
                <div className="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center mb-3">
                    <h3 className="text-lg font-semibold flex items-center gap-2 min-w-0">
                        <ClipboardList className="w-5 h-5 text-text-muted shrink-0" aria-hidden />
                        <span className="truncate">Orden n° {order.id}</span>
                    </h3>
                    <div className="shrink-0">
                        <OrderStatusBadge estadoCodigo={order.estadoCodigo} />
                    </div>
                </div>

                <div className="flex items-center gap-2 mb-1">
                    {patente && (
                        <span className="bg-bg-secondary text-text-main font-mono font-bold text-sm px-2.5 py-0.5 rounded tracking-wide shrink-0">
                            {patente}
                        </span>
                    )}
                    <span className="text-text-main text-sm truncate">
                        {vehicleLabel ?? `Vehículo N°${order.vehicleId}`}
                    </span>
                </div>
                <div className="text-sm text-text-muted mb-4">
                    Actualizada el {formatDate(order.actualizadoEn)}
                </div>

                {mechanicName && (
                    <div className="flex items-center gap-2 text-sm bg-bg-secondary rounded-lg px-3 py-2 mb-4">
                        <User className="w-4 h-4 text-text-muted" aria-hidden />
                        <span className="truncate">Mecánico: {mechanicName}</span>
                    </div>
                )}

                <Link
                    to={detailPath}
                    className="mt-auto flex items-center justify-center gap-2 bg-surface border border-border-custom text-primary-blue py-2.5 rounded-lg text-sm hover:bg-bg-secondary transition-colors no-underline"
                >
                    <FileText className="w-4 h-4" aria-hidden />
                    Ver detalle
                </Link>
            </div>
        </div>
    );
}