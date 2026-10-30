import type {
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    EvidenciaEntradaCrear,
    TipoArchivoEvidencia,
    UrlDescarga,
} from '@/domain/entities/Evidencia';
import type { EvidenciaPort } from '@/domain/ports/EvidenciaPort';
import type { AxiosProgressEvent } from 'axios';
import apiClient from '../config/apiClient';

// Contrato HTTP de MS4 (evidencia multimedia) a través de la API Gateway. El
// backend usa nombres en español; el dominio del frontend en inglés. La respuesta
// nunca incluye la URL del archivo: para verlo o bajarlo hay que pedir una URL
// prefirmada a `/evidencias/{id}/descarga`.

interface EvidenciaApi {
    evidencia_id: string;
    orden_id: number;
    presupuesto_id: number | null;
    contexto: ContextoEvidencia;
    tipo_archivo: TipoArchivoEvidencia;
    visible_cliente: boolean;
    estado: EstadoEvidencia;
    nombre_original: string;
    content_type: string;
    tamano_bytes: number;
    creada_en: string;
}

interface UrlDescargaApi {
    url: string;
    expira_en: number;
}

function mapEvidenciaApi(evidencia: EvidenciaApi): Evidencia {
    return {
        id: evidencia.evidencia_id,
        orderId: String(evidencia.orden_id),
        presupuestoId: evidencia.presupuesto_id === null ? null : String(evidencia.presupuesto_id),
        contexto: evidencia.contexto,
        tipoArchivo: evidencia.tipo_archivo,
        visibleCliente: evidencia.visible_cliente,
        estado: evidencia.estado,
        nombreOriginal: evidencia.nombre_original,
        contentType: evidencia.content_type,
        tamanoBytes: evidencia.tamano_bytes,
        creadaEn: evidencia.creada_en,
    };
}

class EvidenciaService implements EvidenciaPort {
    async getByOrder(ordenId: string): Promise<Evidencia[]> {
        const { data } = await apiClient.get<EvidenciaApi[]>('/evidencias', {
            params: { orden_id: ordenId },
        });
        return data.map(mapEvidenciaApi);
    }

    async getById(evidenciaId: string): Promise<Evidencia> {
        const { data } = await apiClient.get<EvidenciaApi>(`/evidencias/${evidenciaId}`);
        return mapEvidenciaApi(data);
    }

    async getDownloadUrl(evidenciaId: string): Promise<UrlDescarga> {
        const { data } = await apiClient.get<UrlDescargaApi>(`/evidencias/${evidenciaId}/descarga`);
        return { url: data.url, expiraEn: data.expira_en };
    }

    async crear(
        entrada: EvidenciaEntradaCrear,
        onProgress?: (porcentaje: number) => void
    ): Promise<Evidencia> {
        const form = new FormData();
        form.append('archivo', entrada.archivo);
        form.append('orden_id', entrada.ordenId);
        form.append('contexto', entrada.contexto);
        if (entrada.presupuestoId) {
            form.append('presupuesto_id', entrada.presupuestoId);
        }
        if (entrada.visibleCliente !== undefined) {
            form.append('visible_cliente', String(entrada.visibleCliente));
        }

        // No se fija `Content-Type`: axios lo elimina para FormData y deja que el
        // navegador agregue el boundary del multipart.
        const { data } = await apiClient.post<EvidenciaApi>('/evidencias', form, {
            onUploadProgress: (evento: AxiosProgressEvent) => {
                if (!onProgress) return;
                const total = evento.total ?? 0;
                if (total <= 0) return;
                onProgress(Math.min(100, Math.round((evento.loaded / total) * 100)));
            },
        });
        return mapEvidenciaApi(data);
    }
}

export const evidenciaService = new EvidenciaService();
