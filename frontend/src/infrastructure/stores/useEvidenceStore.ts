import { create } from 'zustand';
import type { Evidencia } from '@/domain/entities/Evidencia';
import { initialAsyncStatus, type AsyncStatus, mergeById } from '@/infrastructure/stores/asyncCollection';
import {
    getApiErrorMessage,
    getApiErrorRequestId,
    isNotFoundError,
    isOfflineError,
} from '@/infrastructure/api/errors';

export interface FetchEvidenciasResult {
    evidencias: Evidencia[];
    /** El backend confirmó con 404 que la orden no existe o no es del cliente. */
    notFound: boolean;
    /** El fetch falló y no hay copia local que mostrar. */
    failed: boolean;
}

interface EvidenceState extends AsyncStatus {
    evidencias: Evidencia[];
    /** Evidencias visibles de una orden. */
    fetchByOrder: (
        ordenId: string,
        loader: (ordenId: string) => Promise<Evidencia[]>
    ) => Promise<FetchEvidenciasResult>;
    reset: () => void;
}

// Caché en memoria del portal. Las URLs de descarga (prefirmadas y efímeras) NO
// viven acá: se piden cada vez que se muestra o baja un archivo.
export const useEvidenceStore = create<EvidenceState>((set, get) => ({
    evidencias: [],
    ...initialAsyncStatus,

    fetchByOrder: async (ordenId, loader) => {
        try {
            const evidencias = await loader(ordenId);
            set((state) => ({
                evidencias: mergeById(state.evidencias, evidencias),
                error: null,
                isOffline: false,
                requestId: null,
            }));
            return { evidencias, notFound: false, failed: false };
        } catch (err) {
            if (isNotFoundError(err)) {
                return { evidencias: [], notFound: true, failed: false };
            }
            const local = get().evidencias.filter((evidencia) => evidencia.orderId === ordenId);
            set({
                error: getApiErrorMessage(err),
                isOffline: isOfflineError(err),
                requestId: getApiErrorRequestId(err),
            });
            return { evidencias: local, notFound: false, failed: local.length === 0 };
        }
    },

    reset: () => set({ evidencias: [], ...initialAsyncStatus }),
}));
