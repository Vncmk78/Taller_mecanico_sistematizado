import type { Evidencia, UrlDescarga } from '../entities/Evidencia';

export interface EvidenciaPort {
    /** Evidencias visibles de una orden (404 si la orden no es del cliente). */
    getByOrder(ordenId: string): Promise<Evidencia[]>;
    /** Detalle de una evidencia (misma visibilidad que el listado). */
    getById(evidenciaId: string): Promise<Evidencia>;
    /** URL prefirmada, efímera, para ver o descargar el archivo. */
    getDownloadUrl(evidenciaId: string): Promise<UrlDescarga>;
}
