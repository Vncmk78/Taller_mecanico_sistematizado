import { Bot, Clock, History, MessageSquare, UserCircle2 } from 'lucide-react';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { ordenStatusLabel } from '@/domain/entities/Order';
import { formatDateTime, estadoDotClasses } from '@/presentation/utils/orderDisplay';
import { OrderStatusBadge } from './OrderStatusBadge';

interface OrderHistoryTimelineProps {
    entries: OrderHistoryEntry[];
    loading: boolean;
}

const skeletonRows = [
    'w-2/3 bg-white/10',
    'w-5/6 bg-white/10',
    'w-3/4 bg-white/10',
];

/**
 * Timeline vertical con los cambios de estado de una orden, más recientes
 * primero. Cada entrada muestra el estado al que se movió, el anterior, la
 * fecha, el responsable (usuario o sistema) y la observación registrada.
 */
export function OrderHistoryTimeline({ entries, loading }: OrderHistoryTimelineProps) {
    return (
        <section aria-labelledby="order-history-title" className="glass-card p-6">
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
                            <span className="h-3.5 w-3.5 rounded-full bg-white/10" aria-hidden />
                            <div className={`h-4 rounded ${width}`} />
                        </div>
                    ))}
                </div>
            ) : entries.length === 0 ? (
                <p className="text-sm text-text-muted">
                    Aún no hay registros del historial de estados de esta orden.
                </p>
            ) : (
                <div className="relative pl-6">
                    <span aria-hidden className="absolute left-1 top-3 bottom-3 w-px bg-border-custom" />
                    {entries.map((entry) => (
                        <div key={entry.id} className="relative pb-6 last:pb-0">
                            <span
                                aria-hidden
                                className={`absolute -left-[15px] top-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-black/40 ${
                                    estadoDotClasses[entry.estadoNuevoCodigo] ?? 'bg-white/40'
                                }`}
                            />
                            <div className="flex flex-wrap items-center gap-2">
                                <OrderStatusBadge estadoCodigo={entry.estadoNuevoCodigo} />
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
                                <p className="flex items-start gap-2 mt-2 rounded-lg bg-white/5 px-4 py-2.5 text-sm text-text-muted">
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