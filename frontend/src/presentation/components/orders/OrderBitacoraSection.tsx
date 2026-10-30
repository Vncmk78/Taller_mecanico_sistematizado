import { Wrench } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderBitacoraStore } from '@/infrastructure/stores/useOrderBitacoraStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { useOrderBitacora } from '@/presentation/hooks/useOrderBitacora';
import { BitacoraForm } from './BitacoraForm';
import { OrderBitacoraTimeline } from './OrderBitacoraTimeline';

interface OrderBitacoraSectionProps {
    order: Order;
    /** El rol actual puede registrar entradas (mecánico responsable). */
    canWrite?: boolean;
}

/**
 * Bitácora de trabajo de una orden: el mecánico registra observaciones y
 * acciones (con sus repuestos) y todos los roles ven el listado. Sigue el mismo
 * manejo de errores que el resto del detalle: banner offline para fallos de
 * transporte y alerta reintentable para errores del servidor.
 */
export function OrderBitacoraSection({ order, canWrite = false }: OrderBitacoraSectionProps) {
    const { entries, loading, refetch } = useOrderBitacora(order.id, (ordenId) =>
        orderService.getOrderBitacora(ordenId)
    );
    const isOffline = useOrderBitacoraStore((s) => s.isOffline);
    const error = useOrderBitacoraStore((s) => s.error);
    const requestId = useOrderBitacoraStore((s) => s.requestId);

    return (
        <section className="card p-6 mt-6" aria-labelledby="order-bitacora-title">
            <h3
                id="order-bitacora-title"
                className="text-xl font-semibold flex items-center gap-2 mb-6"
            >
                <Wrench className="w-5 h-5 text-text-muted" aria-hidden />
                Bitácora de trabajo
            </h3>

            {isOffline && <OfflineBanner message={error} onRetry={refetch} requestId={requestId} className="mb-6" />}
            {!isOffline && error && (
                <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
                    {error} Se muestran las últimas entradas disponibles.
                    {requestId && (
                        <span className="block mt-1 font-mono text-xs opacity-80">Referencia: {requestId}</span>
                    )}
                </Alert>
            )}

            {canWrite && (
                <BitacoraForm
                    ordenId={order.id}
                    className="mb-6 border-b border-border-custom pb-6"
                />
            )}

            <OrderBitacoraTimeline entries={entries} loading={loading} failed={isOffline || !!error} />
        </section>
    );
}
