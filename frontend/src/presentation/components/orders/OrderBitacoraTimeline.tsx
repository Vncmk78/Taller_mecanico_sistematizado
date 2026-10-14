import { Clock, Package, UserCircle2, Wrench } from 'lucide-react';
import type { BitacoraEntry, TipoBitacora } from '@/domain/entities/Bitacora';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { formatDateTime } from '@/presentation/utils/orderDisplay';

interface OrderBitacoraTimelineProps {
    entries: BitacoraEntry[];
    loading: boolean;
    failed?: boolean;
}

const tipoEstilos: Record<TipoBitacora, string> = {
    accion: 'bg-status-orange/15 text-status-orange border-status-orange/40',
    observacion: 'bg-status-blue/15 text-status-blue border-status-blue/40',
};

const tipoDots: Record<TipoBitacora, string> = {
    accion: 'bg-status-orange',
    observacion: 'bg-status-blue',
};

const tipoEtiquetas: Record<TipoBitacora, string> = {
    accion: 'Acción',
    observacion: 'Observación',
};

const skeletonRows = [
    'w-2/3 bg-bg-secondary',
    'w-3/4 bg-bg-secondary',
    'w-1/2 bg-bg-secondary',
];

/**
 * Bitácora de trabajo del mecánico: lista (más reciente primero) de
 * observaciones y acciones, con los repuestos utilizados cuando los hay.
 */
export function OrderBitacoraTimeline({ entries, loading, failed = false }: OrderBitacoraTimelineProps) {
    return (
        <div>
            {loading ? (
                <div className="space-y-6 animate-pulse" aria-label="Cargando bitácora">
                    {skeletonRows.map((width) => (
                        <div key={width} className="flex items-start gap-3">
                            <span className="h-3.5 w-3.5 rounded-full bg-bg-secondary" aria-hidden />
                            <span className={`h-4 rounded ${width}`} aria-hidden />
                        </div>
                    ))}
                </div>
            ) : entries.length === 0 ? (
                failed ? (
                    <p className="text-sm text-text-muted">
                        No se pudo cargar la bitácora de trabajo.
                    </p>
                ) : (
                    <EmptyState
                        className="p-0"
                        icon={Wrench}
                        title="Sin entradas en la bitácora."
                        description="Aún no se registran observaciones ni acciones para esta orden."
                    />
                )
            ) : (
                <div className="relative pl-6">
                    <span className="absolute left-[6px] top-2 bottom-2 w-px bg-border-custom" aria-hidden />
                    <ul className="space-y-6">
                        {entries.map((entry) => (
                            <li key={entry.id} className="relative">
                                <span
                                    className={`absolute -left-6 top-1 h-3.5 w-3.5 rounded-full ring-4 ring-surface ${
                                        tipoDots[entry.tipo]
                                    }`}
                                    aria-hidden
                                />
                                <div className="flex flex-wrap items-center gap-2">
                                    <span
                                        className={`text-[11px] px-2 py-0.5 rounded-full border font-semibold ${tipoEstilos[entry.tipo]}`}
                                    >
                                        {tipoEtiquetas[entry.tipo]}
                                    </span>
                                    <span className="inline-flex items-center gap-1.5 text-sm text-text-muted">
                                        <Clock className="w-4 h-4" aria-hidden />
                                        {formatDateTime(entry.creadoEn)}
                                    </span>
                                    <span className="inline-flex items-center gap-1.5 text-sm text-text-muted">
                                        <UserCircle2 className="w-4 h-4" aria-hidden />
                                        Usuario {entry.autorUsuarioId}
                                    </span>
                                </div>
                                <p className="mt-2 text-text-main whitespace-pre-line">{entry.descripcion}</p>
                                {entry.repuestos.length > 0 && (
                                    <ul className="mt-2 space-y-1">
                                        {entry.repuestos.map((repuesto, index) => (
                                            <li
                                                key={`${repuesto.nombre}-${index}`}
                                                className="flex items-center gap-2 text-sm text-text-muted"
                                            >
                                                <Package className="w-4 h-4" aria-hidden />
                                                {repuesto.nombre} × {repuesto.cantidad}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
