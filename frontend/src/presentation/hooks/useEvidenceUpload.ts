import { useCallback } from 'react';
import type { Evidencia, EvidenciaEntradaCrear } from '@/domain/entities/Evidencia';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';

export type EvidenciaEntradaSubir = Omit<EvidenciaEntradaCrear, 'ordenId'>;

export interface UseEvidenceUploadResult {
    /** Sube el archivo y agrega la evidencia a la caché; null si falló. */
    subir: (entrada: EvidenciaEntradaSubir) => Promise<Evidencia | null>;
    /** Porcentaje de subida (0-100). */
    progress: number;
    isUploading: boolean;
    success: boolean;
    error: string | null;
    requestId: string | null;
    isOffline: boolean;
    /** Limpia el resultado (éxito/error) para una nueva carga. */
    reset: () => void;
}

/**
 * Estado de la subida de una evidencia de una orden. La carga la ejecuta el
 * store compartido (con el progreso del transporte); este hook liga la orden,
 * traduce el estado a banderas para la vista y expone `subir`.
 */
export function useEvidenceUpload(ordenId: string | undefined): UseEvidenceUploadResult {
    const subirStore = useEvidenceStore((s) => s.subir);
    const reset = useEvidenceStore((s) => s.resetUpload);
    const uploadStatus = useEvidenceStore((s) => s.uploadStatus);
    const progress = useEvidenceStore((s) => s.uploadProgress);
    const uploadError = useEvidenceStore((s) => s.uploadError);
    const requestId = useEvidenceStore((s) => s.uploadRequestId);
    const isOffline = useEvidenceStore((s) => s.uploadIsOffline);

    const subir = useCallback(
        (entrada: EvidenciaEntradaSubir) => {
            if (!ordenId) return Promise.resolve(null);
            return subirStore({ ...entrada, ordenId }, (datos, onProgress) =>
                evidenciaService.crear(datos, onProgress)
            );
        },
        [ordenId, subirStore]
    );

    return {
        subir,
        progress,
        isUploading: uploadStatus === 'uploading',
        success: uploadStatus === 'success',
        error: uploadStatus === 'error' ? uploadError : null,
        requestId,
        isOffline,
        reset,
    };
}