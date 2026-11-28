import type {
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    EvidenciaEntradaCrear,
    TipoArchivoEvidencia,
    UrlDescarga,
} from '@/domain/entities/Evidencia';
import type { EvidenciaPort } from '@/domain/ports/EvidenciaPort';
import apiClient from '../config/apiClient';
import { getToken } from '../config/tokenStorage';
import { obtenerTodasLasPaginas } from './paginacion';

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
        const data = await obtenerTodasLasPaginas<EvidenciaApi>('/evidencias', {
            orden_id: ordenId,
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

        // Subida con `fetch` nativo: el adaptador fetch de axios 1.20 falla con
        // ERR_DNS_NO_MATCHING_SUPPORTED_ALPN al enviar FormData en este entorno,
        // mientras que `fetch` genera directamente el boundary del multipart.
        const token = getToken();
        let respuesta: Response;
        try {
            respuesta = await fetch(`${apiClient.defaults.baseURL}/evidencias`, {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
                body: form,
            });
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') {
                throw error;
            }
            throw new Error('Sin conexión: no se pudo subir la evidencia. Revisa tu red e inténtalo de nuevo.');
        }
        if (!respuesta.ok) {
            const detalle = await respuesta.text();
            throw new Error(detalle || `Error al subir evidencia (${respuesta.status})`);
        }
        onProgress?.(100);
        const data = (await respuesta.json()) as EvidenciaApi;
        return mapEvidenciaApi(data);
    }
}

export const evidenciaService = new EvidenciaService();
