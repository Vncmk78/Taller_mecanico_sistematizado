import { useEffect, useState } from 'react';
import type { Evidencia } from '@/domain/entities/Evidencia';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';

export interface UseOrderEvidenceResult {
    evidencias: Evidencia[];
    /** El listado está cargado (aunque venga vacío). */
    loading: boolean;
    /** El backend confirmó que la orden no existe o no es del cliente. */
    notFound: boolean;
    /** El fetch falló y no hay copia local: la vista debe ofrecer reintento. */
    failed: boolean;
    error: string | null;
    isOffline: boolean;
    requestId: string | null;
    refetch: () => void;
}

/**
 * Evidencia multimedia de una orden. `loading` se deriva de la clave de la
 * petición en curso, sin disparar renders desde el efecto (mismo patrón que
 * useBudgetDetail).
 */
export function useOrderEvidence(ordenId: string | undefined): UseOrderEvidenceResult {
    const evidencias = useEvidenceStore((s) => s.evidencias);
    const fetchByOrder = useEvidenceStore((s) => s.fetchByOrder);
    const error = useEvidenceStore((s) => s.error);
    const isOffline = useEvidenceStore((s) => s.isOffline);
    const requestId = useEvidenceStore((s) => s.requestId);

    const [reloadKey, setReloadKey] = useState(0);
    const [completedKey, setCompletedKey] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);
    const [failed, setFailed] = useState(false);
    const requestKey = `${ordenId ?? ''}:${reloadKey}`;

    useEffect(() => {
        if (!ordenId) return;
        let active = true;

        (async () => {
            const result = await fetchByOrder(ordenId, (id) => evidenciaService.getByOrder(id));
            if (!active) return;
            setNotFound(result.notFound);
            setFailed(result.failed);
            setCompletedKey(requestKey);
        })();

        return () => {
            active = false;
        };
    }, [ordenId, requestKey, fetchByOrder]);

    const sinOrden = !ordenId;
    return {
        evidencias: sinOrden ? [] : evidencias.filter((cached) => cached.orderId === ordenId),
        loading: !sinOrden && completedKey !== requestKey,
        notFound: sinOrden ? true : notFound,
        failed: sinOrden ? false : failed,
        error,
        isOffline,
        requestId,
        refetch: () => setReloadKey((key) => key + 1),
    };
}
