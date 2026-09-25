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
        <div className="glass-card p-0 overflow-hidden flex flex-col">
            <div className="p-5 flex-grow flex flex-col">
                <div className="flex justify-between items-center gap-3 mb-3">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <ClipboardList className="w-5 h-5 text-text-muted shrink-0" />
                        <span className="truncate">Orden n° {order.id}</span>
                    </h3>
                    <OrderStatusBadge estadoCodigo={order.estadoCodigo} />
                </div>

                <div className="flex items-center gap-2 mb-1">
                    {patente && (
                        <span className="bg-white/90 text-black font-mono font-bold text-sm px-2.5 py-0.5 rounded tracking-wide shrink-0">
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
                    <div className="flex items-center gap-2 text-sm bg-white/5 rounded-lg px-3 py-2 mb-4">
                        <User className="w-4 h-4 text-text-muted" />
                        <span className="truncate">Mecánico: {mechanicName}</span>
                    </div>
                )}

                <Link
                    to={detailPath}
                    className="mt-auto flex items-center justify-center gap-2 bg-white/5 border border-border-custom text-white py-2.5 rounded-lg text-sm hover:bg-white/15 transition-colors no-underline"
                >
                    <FileText className="w-4 h-4" />
                    Ver detalle
                </Link>
            </div>
        </div>
    );
}