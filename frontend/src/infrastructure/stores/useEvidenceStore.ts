import { create } from 'zustand';
import type { Evidencia, EvidenciaEntradaCrear } from '@/domain/entities/Evidencia';
import { initialAsyncStatus, type AsyncStatus, mergeById, upsertById } from '@/infrastructure/stores/asyncCollection';
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

export type EvidenciaUploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export interface EvidenciaUploadState {
    uploadStatus: EvidenciaUploadStatus;
    /** Porcentaje de subida (0-100) mientras `uploadStatus === 'uploading'`. */
    uploadProgress: number;
    uploadError: string | null;
    uploadRequestId: string | null;
    uploadIsOffline: boolean;
}

export const initialUploadState: EvidenciaUploadState = {
    uploadStatus: 'idle',
    uploadProgress: 0,
    uploadError: null,
    uploadRequestId: null,
    uploadIsOffline: false,
};

interface EvidenceState extends AsyncStatus, EvidenciaUploadState {
    evidencias: Evidencia[];
    /** Evidencias visibles de una orden. */
    fetchByOrder: (
        ordenId: string,
        loader: (ordenId: string) => Promise<Evidencia[]>
    ) => Promise<FetchEvidenciasResult>;
    /** Sube una evidencia y la agrega a la caché; null si falló (ver upload*). */
    subir: (
        entrada: EvidenciaEntradaCrear,
        loader: (
            entrada: EvidenciaEntradaCrear,
            onProgress: (porcentaje: number) => void
        ) => Promise<Evidencia>
    ) => Promise<Evidencia | null>;
    resetUpload: () => void;
    reset: () => void;
}

// Caché en memoria del portal. Las URLs de descarga (prefirmadas y efímeras) NO
// viven acá: se piden cada vez que se muestra o baja un archivo.
export const useEvidenceStore = create<EvidenceState>((set, get) => ({
    evidencias: [],
    ...initialAsyncStatus,
    ...initialUploadState,

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

    subir: async (entrada, loader) => {
        // Un solo envío a la vez: evita subidas duplicadas por doble clic.
        if (get().uploadStatus === 'uploading') return null;

        set({ uploadStatus: 'uploading', uploadProgress: 0, uploadError: null, uploadRequestId: null, uploadIsOffline: false });
        try {
            const evidencia = await loader(entrada, (porcentaje) =>
                set({ uploadProgress: porcentaje })
            );
            set((state) => ({
                evidencias: upsertById(state.evidencias, evidencia),
                uploadStatus: 'success',
                uploadProgress: 100,
                uploadError: null,
                uploadRequestId: null,
                uploadIsOffline: false,
            }));
            return evidencia;
        } catch (err) {
            set({
                uploadStatus: 'error',
                uploadError: getApiErrorMessage(err),
                uploadRequestId: getApiErrorRequestId(err),
                uploadIsOffline: isOfflineError(err),
            });
            return null;
        }
    },

    resetUpload: () => set({ ...initialUploadState }),

    reset: () => set({ evidencias: [], ...initialAsyncStatus, ...initialUploadState }),
}));
