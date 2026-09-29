import { CalendarDays, ClipboardList, Clock, Hash, User, Wrench } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { formatDateTime } from '@/presentation/utils/orderDisplay';

interface OrderDetailPanelProps {
    order: Order;
    patente?: string;
    vehicleLabel?: string;
}

export function OrderDetailPanel({ order, patente, vehicleLabel }: OrderDetailPanelProps) {
    return (
        <div className="glass-card p-6">
            <div className="flex justify-between items-center gap-3 mb-6 pb-4 border-b border-border-custom flex-wrap">
                <h3 className="text-xl font-semibold flex items-center gap-2">
                    <ClipboardList className="w-5 h-5 text-text-muted" />
                    Orden de trabajo n° {order.id}
                </h3>
                <OrderStatusBadge estadoCodigo={order.estadoCodigo} />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                    <span className="text-text-muted text-sm block mb-1">Vehículo</span>
                    <div className="flex items-center gap-2">
                        {patente && (
                            <span className="bg-white/90 text-black font-mono font-bold text-sm px-2.5 py-1 rounded tracking-wide shrink-0">
                                {patente}
                            </span>
                        )}
                        <span className="text-lg font-medium truncate">
                            {vehicleLabel ?? `Vehículo N°${order.vehicleId}`}
                        </span>
                    </div>
                </div>

                <div>
                    <span className="text-text-muted text-sm block mb-1">Mecánico asignado</span>
                    <div className="flex items-center gap-2 text-lg font-medium">
                        <Wrench className="w-4 h-4 text-text-muted shrink-0" />
                        {order.mecanicoNombre ??
                            (order.mecanicoActualId ? `Mecánico ${order.mecanicoActualId}` : 'Sin asignar')}
                    </div>
                </div>

                <div>
                    <span className="text-text-muted text-sm block mb-1">Ingreso (ficha n°)</span>
                    <div className="flex items-center gap-2 text-lg font-medium">
                        <Hash className="w-4 h-4 text-text-muted shrink-0" />
                        {order.ingresoId}
                    </div>
                </div>

                <div>
                    <span className="text-text-muted text-sm block mb-1">Creada por (usuario)</span>
                    <div className="flex items-center gap-2 text-lg font-medium">
                        <User className="w-4 h-4 text-text-muted shrink-0" />
                        {order.creadoPorId}
                    </div>
                </div>

                <div>
                    <span className="text-text-muted text-sm block mb-1">Creada el</span>
                    <div className="flex items-center gap-2 text-base font-medium">
                        <CalendarDays className="w-4 h-4 text-text-muted shrink-0" />
                        {formatDateTime(order.creadoEn)}
                    </div>
                </div>

                <div>
                    <span className="text-text-muted text-sm block mb-1">Última actualización</span>
                    <div className="flex items-center gap-2 text-base font-medium">
                        <Clock className="w-4 h-4 text-text-muted shrink-0" />
                        {formatDateTime(order.actualizadoEn)}
                    </div>
                </div>
            </div>
        </div>
    );
}