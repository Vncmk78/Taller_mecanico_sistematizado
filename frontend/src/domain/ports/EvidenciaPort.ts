import type { Evidencia, EvidenciaEntradaCrear, UrlDescarga } from '../entities/Evidencia';

export interface EvidenciaPort {
    /** Evidencias visibles de una orden (404 si la orden no es del cliente). */
    getByOrder(ordenId: string): Promise<Evidencia[]>;
    /** Detalle de una evidencia (misma visibilidad que el listado). */
    getById(evidenciaId: string): Promise<Evidencia>;
    /** URL prefirmada, efímera, para ver o bajar el archivo. */
    getDownloadUrl(evidenciaId: string): Promise<UrlDescarga>;

    /**
     * Sube una evidencia (solo Mecánico/Administrador). `onProgress` recibe el
     * porcentaje de subida (0-100) mientras el archivo viaja al servidor.
     */
    crear(
        entrada: EvidenciaEntradaCrear,
        onProgress?: (porcentaje: number) => void
    ): Promise<Evidencia>;
}
