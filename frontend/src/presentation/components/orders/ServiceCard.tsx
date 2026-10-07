import { Link } from 'react-router-dom';
import { Car, Clock, FileText, Wrench } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { formatDate } from '@/presentation/utils/orderDisplay';

interface ServiceCardProps {
    order: Order;
    detailPath: string;
    vehiclePath: string;
    patente?: string;
    vehicleLabel?: string;
    /** Estado que requiere acción del cliente (p. ej. presupuesto por aprobar). */
    requiresAttention?: boolean;
    attentionLabel?: string;
}

export function ServiceCard({
    order,
    detailPath,
    vehiclePath,
    patente,
    vehicleLabel,
    requiresAttention = false,
    attentionLabel,
}: ServiceCardProps) {
    return (
        <div
            className={`card p-0 overflow-hidden flex flex-col ${
                requiresAttention ? 'border-status-orange/70 shadow-[0_0_18px_rgba(242,106,46,0.15)]' : ''
            }`}
        >
            <div className="p-5 flex-grow flex flex-col gap-3">
                <div className="flex justify-between items-center gap-3">
                    <h3 className="text-lg font-semibold flex items-center gap-2 min-w-0">
                        <Wrench className="w-5 h-5 text-text-muted shrink-0" aria-hidden />
                        <span className="truncate">Servicio n° {order.id}</span>
                    </h3>
                    <OrderStatusBadge estadoCodigo={order.estadoCodigo} className="shrink-0" />
                </div>

                <div className="flex items-center gap-2">
                    {patente && (
                        <span className="bg-bg-secondary text-text-main font-mono font-bold text-sm px-2.5 py-0.5 rounded tracking-wide shrink-0">
                            {patente}
                        </span>
                    )}
                    <span className="text-text-main text-sm truncate">{vehicleLabel ?? `Vehículo N°${order.vehicleId}`}</span>
                </div>

                <div className="flex items-center gap-2 text-sm text-text-muted">
                    <Clock className="w-4 h-4 shrink-0" aria-hidden />
                    Actualizada el {formatDate(order.actualizadoEn)}
                </div>

                {requiresAttention && (
                    <p className="text-sm font-semibold text-status-orange bg-status-orange/10 border border-status-orange/30 rounded-lg px-3 py-2">
                        {attentionLabel ?? 'Requiere su atención'}
                    </p>
                )}

                <div className="mt-auto flex items-center gap-2">
                    <Link
                        to={detailPath}
                        className="flex-1 flex items-center justify-center gap-2 bg-primary-blue text-white py-2.5 rounded-lg text-sm font-bold hover:bg-primary-blue-hover transition-colors no-underline"
                    >
                        <FileText className="w-4 h-4" aria-hidden />
                        Ver detalle
                    </Link>
                    <Link
                        to={vehiclePath}
                        className="flex items-center justify-center gap-2 bg-surface border border-border-custom text-primary-blue py-2.5 rounded-lg text-sm hover:bg-bg-secondary transition-colors no-underline"
                        title="Ver ficha del vehículo"
                    >
                        <Car className="w-4 h-4" aria-hidden />
                        <span className="hidden sm:inline">Vehículo</span>
                    </Link>
                </div>
            </div>
        </div>
    );
}