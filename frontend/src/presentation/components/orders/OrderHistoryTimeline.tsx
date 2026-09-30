import { Bot, Clock, History, MessageSquare, UserCircle2 } from 'lucide-react';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { ordenStatusLabel } from '@/domain/entities/Order';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { formatDateTime, estadoDotClasses } from '@/presentation/utils/orderDisplay';
import { OrderStatusBadge } from './OrderStatusBadge';

interface OrderHistoryTimelineProps {
    entries: OrderHistoryEntry[];
    loading: boolean;
    /** El fetch del historial falló: no se debe presentar como "aún sin registros". */
    failed?: boolean;
}

const skeletonRows = [
    'w-2/3 bg-bg-secondary',
    'w-5/6 bg-bg-secondary',
    'w-3/4 bg-bg-secondary',
];

/**
 * Timeline vertical con los cambios de estado de una orden, más recientes
 * primero. Cada entrada muestra el estado al que se movió, el anterior, la
 * fecha, el responsable (usuario o sistema) y la observación registrada.
 */
export function OrderHistoryTimeline({ entries, loading, failed = false }: OrderHistoryTimelineProps) {
    return (
        <section aria-labelledby="order-history-title" className="card p-6">
            <h3
                id="order-history-title"
                className="text-xl font-semibold flex items-center gap-2 mb-6"
            >
                <History className="w-5 h-5 text-text-muted" aria-hidden />
                Historial de estados
            </h3>

            {loading ? (
                <div className="space-y-6 animate-pulse" aria-label="Cargando historial">
                    {skeletonRows.map((width) => (
                        <div key={width} className="flex items-start gap-3">
                            <span className="h-3.5 w-3.5 rounded-full bg-bg-secondary" aria-hidden />
                            <div className={`h-4 rounded ${width}`} />
                        </div>
                    ))}
                </div>
            ) : entries.length === 0 ? (
                failed ? (
                    <p className="text-sm text-text-muted">
                        No fue posible mostrar el historial de estados de esta orden.
                    </p>
                ) : (
                    <EmptyState
                        className="!py-6 !px-0"
                        icon={History}
                        title="Aún no hay registros del historial de estados de esta orden."
                    />
                )
            ) : (
                <div className="relative pl-6">
                    <span aria-hidden className="absolute left-1 top-3 bottom-3 w-px bg-border-custom" />
                    {entries.map((entry) => (
                        <div key={entry.id} className="relative pb-6 last:pb-0">
                            <span
                                aria-hidden
                                className={`absolute -left-[15px] top-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-surface ${
                                    estadoDotClasses[entry.estadoNuevoCodigo] ?? 'bg-bg-secondary'
                                }`}
                            />
                            <div className="flex flex-wrap items-center gap-2">
                                <OrderStatusBadge estadoCodigo={entry.estadoNuevoCodigo} size="sm" />
                                {entry.estadoAnteriorCodigo !== null && (
                                    <span className="text-sm text-text-muted">
                                        desde {ordenStatusLabel(entry.estadoAnteriorCodigo)}
                                    </span>
                                )}
                            </div>
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-text-muted">
                                <span className="inline-flex items-center gap-1.5">
                                    <Clock className="w-4 h-4" aria-hidden />
                                    {formatDateTime(entry.fecha)}
                                </span>
                                <span className="inline-flex items-center gap-1.5">
                                    {entry.origen === 'sistema' ? (
                                        <Bot className="w-4 h-4" aria-hidden />
                                    ) : (
                                        <UserCircle2 className="w-4 h-4" aria-hidden />
                                    )}
                                    {entry.origen === 'usuario'
                                        ? (entry.usuarioNombre ?? `Usuario ${entry.actorUsuarioId ?? '?'}`)
                                        : 'Sistema'}
                                </span>
                            </div>
                            {entry.observacion && (
                                <p className="flex items-start gap-2 mt-2 rounded-lg bg-bg-secondary px-4 py-2.5 text-sm text-text-muted">
                                    <MessageSquare className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
                                    {entry.observacion}
                                </p>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}