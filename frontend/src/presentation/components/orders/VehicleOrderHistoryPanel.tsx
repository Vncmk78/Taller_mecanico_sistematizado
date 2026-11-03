import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardList } from 'lucide-react';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { Alert } from '@/presentation/components/ui/Alert';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { OrderStatusBadge } from '@/presentation/components/orders/OrderStatusBadge';
import { formatDate } from '@/presentation/utils/orderDisplay';

const PAGE_SIZE = 20;

interface VehicleOrderHistoryPanelProps {
    vehicleId: string;
    detailPathPrefix: string;
    vehicleLabel?: string;
}

export function VehicleOrderHistoryPanel({
    vehicleId,
    detailPathPrefix,
    vehicleLabel,
}: VehicleOrderHistoryPanelProps) {
    const [orders, setOrders] = useState<Order[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        let cancelled = false;

        orderService
            .getVehicleOrderHistory(vehicleId, { limit: PAGE_SIZE, offset })
            .then((page) => {
                if (cancelled) return;
                setError(null);
                setOrders(page.items);
                setTotal(page.total);
            })
            .catch((cause: unknown) => {
                if (cancelled) return;
                setError(getApiErrorMessage(cause, 'No se pudo cargar el historial del vehículo.'));
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [vehicleId, offset, retry]);

    const start = total === 0 ? 0 : offset + 1;
    const end = Math.min(offset + PAGE_SIZE, total);

    return (
        <section className="card" aria-labelledby="vehicle-order-history-title">
            <h3
                id="vehicle-order-history-title"
                className="text-xl font-semibold flex items-center justify-between gap-2 mb-4 pb-4 border-b border-border-custom"
            >
                <span className="flex items-center gap-2">
                    <ClipboardList className="w-5 h-5 text-text-muted" aria-hidden />
                    Historial de Órdenes
                </span>
                {!loading && !error && total > 0 && (
                    <span className="text-sm font-normal text-text-muted">
                        {total} {total === 1 ? 'orden' : 'órdenes'}
                    </span>
                )}
            </h3>

            {loading ? (
                <p className="text-text-muted text-sm py-6 text-center" role="status">
                    Cargando historial de mantención...
                </p>
            ) : error ? (
                <Alert
                    tone="error"
                    action={
                        <RetryButton
                            tone="error"
                            onClick={() => {
                                setLoading(true);
                                setRetry((value) => value + 1);
                            }}
                        />
                    }
                >
                    {error}
                </Alert>
            ) : total === 0 ? (
                <p className="text-text-muted text-sm py-6 text-center">
                    Este vehículo aún no tiene órdenes de trabajo registradas.
                </p>
            ) : (
                <>
                    <ul className="flex flex-col gap-3" aria-label="Historial de órdenes del vehículo">
                        {orders.map((order) => (
                            <li key={order.id}>
                                <Link
                                    to={`${detailPathPrefix}/${order.id}`}
                                    className="flex items-center justify-between gap-3 bg-bg-secondary rounded-lg px-4 py-3 hover:bg-surface no-underline transition-colors"
                                >
                                    <div className="min-w-0">
                                        <p className="text-text-main font-semibold truncate">
                                            Orden n° {order.id}
                                            {vehicleLabel ? ` · ${vehicleLabel}` : ''}
                                        </p>
                                        <p className="text-text-muted text-sm">
                                            Ingresó el {formatDate(order.creadoEn)}
                                        </p>
                                    </div>
                                    <OrderStatusBadge
                                        estadoCodigo={order.estadoCodigo}
                                        variant="dot"
                                        size="sm"
                                        className="shrink-0"
                                    />
                                </Link>
                            </li>
                        ))}
                    </ul>

                    {total > PAGE_SIZE && (
                        <div className="mt-4 flex items-center justify-between gap-3">
                            <p className="text-text-muted text-sm" aria-live="polite">
                                {start}–{end} de {total}
                            </p>
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    className="rounded-md border border-border-custom px-3 py-1.5 text-sm text-primary-blue disabled:cursor-not-allowed disabled:opacity-50"
                                    disabled={offset === 0 || loading}
                                    onClick={() => {
                                        setLoading(true);
                                        setOffset((value) => Math.max(0, value - PAGE_SIZE));
                                    }}
                                >
                                    Anterior
                                </button>
                                <button
                                    type="button"
                                    className="rounded-md border border-border-custom px-3 py-1.5 text-sm text-primary-blue disabled:cursor-not-allowed disabled:opacity-50"
                                    disabled={offset + PAGE_SIZE >= total || loading}
                                    onClick={() => {
                                        setLoading(true);
                                        setOffset((value) => value + PAGE_SIZE);
                                    }}
                                >
                                    Siguiente
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </section>
    );
}
