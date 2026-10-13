import { useEffect, useState } from 'react';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useBudgetStore } from '@/infrastructure/stores/useBudgetStore';

export interface UseBudgetDetailResult {
    presupuesto: Presupuesto | undefined;
    /** El presupuesto está cargado con sus versiones e ítems (listo para decidir). */
    loading: boolean;
    notFound: boolean;
    /** El fetch falló y no hay copia local: la vista debe ofrecer reintento. */
    failed: boolean;
    error: string | null;
    isOffline: boolean;
    requestId: string | null;
    refetch: () => void;
}

/**
 * Detalle del presupuesto de una orden: primero resuelve el presupuesto por
 * `orden_id` (listado acotado) y luego trae su detalle con versiones e ítems.
 * Se considera fallo si el detalle no llegó (solo quedó el resumen en caché),
 * para no mostrar un presupuesto sin partidas. `loading` se deriva de la clave
 * de la petición en curso, sin disparar renders desde el efecto.
 */
export function useBudgetDetail(ordenId: string | undefined): UseBudgetDetailResult {
    const presupuestos = useBudgetStore((s) => s.presupuestos);
    const fetchByOrder = useBudgetStore((s) => s.fetchByOrder);
    const fetchById = useBudgetStore((s) => s.fetchById);
    const error = useBudgetStore((s) => s.error);
    const isOffline = useBudgetStore((s) => s.isOffline);
    const requestId = useBudgetStore((s) => s.requestId);

    const [reloadKey, setReloadKey] = useState(0);
    const [completedKey, setCompletedKey] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);
    const [failed, setFailed] = useState(false);
    const requestKey = `${ordenId ?? ''}:${reloadKey}`;

    useEffect(() => {
        if (!ordenId) return;
        let active = true;

        (async () => {
            const resumen = await fetchByOrder(ordenId, (id) => presupuestoService.getByOrder(id));
            if (!active) return;
            if (resumen.failed) {
                setNotFound(false);
                setFailed(true);
                setCompletedKey(requestKey);
                return;
            }
            if (resumen.notFound || !resumen.presupuesto) {
                setFailed(false);
                setNotFound(true);
                setCompletedKey(requestKey);
                return;
            }
            const detalle = await fetchById(resumen.presupuesto.id, (id) =>
                presupuestoService.getById(id)
            );
            if (!active) return;
            const sinPartidas = detalle.presupuesto !== null && detalle.presupuesto.versiones.length === 0;
            setNotFound(false);
            setFailed(detalle.failed || detalle.notFound || sinPartidas);
            setCompletedKey(requestKey);
        })();

        return () => {
            active = false;
        };
    }, [ordenId, requestKey, fetchByOrder, fetchById]);

    const sinOrden = !ordenId;
    return {
        presupuesto: sinOrden ? undefined : presupuestos.find((cached) => cached.orderId === ordenId),
        loading: !sinOrden && completedKey !== requestKey,
        notFound: sinOrden ? true : notFound,
        failed: sinOrden ? false : failed,
        error,
        isOffline,
        requestId,
        refetch: () => setReloadKey((key) => key + 1),
    };
}
