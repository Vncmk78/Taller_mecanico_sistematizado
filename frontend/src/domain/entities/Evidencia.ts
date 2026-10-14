// Evidencia multimedia de una orden (MS4). Espejo del contrato de la API Gateway
// (EvidenciaRespuesta). El archivo vive en un almacenamiento de objetos privado:
// la respuesta nunca trae la URL ni la clave del objeto, solo metadatos. Para ver
// o descargar el archivo se pide una URL prefirmada (ver `UrlDescarga`).

export type ContextoEvidencia = 'diagnostico' | 'presupuesto' | 'reparacion' | 'resultado_final';
export type TipoArchivoEvidencia = 'foto' | 'video';
export type EstadoEvidencia = 'pendiente' | 'confirmada' | 'anulada';

export const CONTEXTO_EVIDENCIA_LABEL: Record<ContextoEvidencia, string> = {
    diagnostico: 'Diagnóstico',
    presupuesto: 'Presupuesto',
    reparacion: 'Reparación',
    resultado_final: 'Resultado final',
};

export function contextoEvidenciaLabel(contexto: ContextoEvidencia): string {
    return CONTEXTO_EVIDENCIA_LABEL[contexto] ?? contexto;
}

export interface Evidencia {
    id: string;
    orderId: string;
    presupuestoId: string | null;
    contexto: ContextoEvidencia;
    tipoArchivo: TipoArchivoEvidencia;
    /** El cliente solo recibe evidencias marcadas como visibles. */
    visibleCliente: boolean;
    estado: EstadoEvidencia;
    nombreOriginal: string;
    contentType: string;
    tamanoBytes: number;
    creadaEn: string;
}

/**
 * URL prefirmada del almacenamiento para ver o bajar el archivo. Es efímera
 * (`expiraEn` segundos) y no se guarda ni se cachea: se pide cada vez.
 */
export interface UrlDescarga {
    url: string;
    expiraEn: number;
}

/** true si la evidencia es una imagen mostrable en un `<img>`. */
export function esImagen(evidencia: Evidencia): boolean {
    return evidencia.tipoArchivo === 'foto' || evidencia.contentType.startsWith('image/');
}

/** true si la evidencia es un video que se reproduce en un `<video>`. */
export function esVideo(evidencia: Evidencia): boolean {
    return evidencia.tipoArchivo === 'video' || evidencia.contentType.startsWith('video/');
}
