import type {
    DecisionRevision,
    FiltrosSolicitudes,
    PaginaSolicitudes,
    SituacionSolicitud,
    SolicitudNuevaAtencion,
} from '@/domain/entities/SolicitudNuevaAtencion';
import type {
    NuevaAtencionPort,
    ResultadoGeneracion,
    ResultadoSolicitud,
} from '@/domain/ports/NuevaAtencionPort';
import apiClient from '../config/apiClient';
import { mapOrdenApi, type OrdenRespuesta } from './OrderService';

// Contrato acordado de MS2 a través de la Gateway (contrato-web-bloques-3-4.md,
// Entrega B). Todas las propiedades llegan siempre, incluidas las nulas.
interface SolicitudNuevaAtencionApi {
    solicitud_id: number;
    orden_cancelada_id: number;
    vehiculo_id: number;
    cliente_usuario_id: number;
    descripcion: string;
    solicitada_en: string;
    situacion: SituacionSolicitud;
    respuesta: string | null;
    revisor_id: number | null;
    revisada_en: string | null;
    orden_generada_id: number | null;
}

interface PaginaSolicitudesApi {
    items: SolicitudNuevaAtencionApi[];
    total: number;
    limit: number;
    offset: number;
}

interface GeneracionApi {
    solicitud: SolicitudNuevaAtencionApi;
    orden: OrdenRespuesta;
}

/**
 * Una respuesta 200/201 que no trae lo que el contrato garantiza (la revisión
 * con su auditoría, o la orden vinculada a la solicitud). No se presenta como
 * éxito: la pantalla comprueba con el GET de la solicitud.
 */
export class RespuestaIncompletaError extends Error {
    constructor(detalle: string) {
        super(detalle);
        this.name = 'RespuestaIncompletaError';
    }
}

const idONulo = (valor: number | null) => (valor === null ? null : String(valor));

export function mapSolicitudApi(s: SolicitudNuevaAtencionApi): SolicitudNuevaAtencion {
    return {
        id: String(s.solicitud_id),
        ordenCanceladaId: String(s.orden_cancelada_id),
        vehiculoId: String(s.vehiculo_id),
        clienteUsuarioId: String(s.cliente_usuario_id),
        descripcion: s.descripcion,
        solicitadaEn: s.solicitada_en,
        situacion: s.situacion,
        respuesta: s.respuesta,
        revisorId: idONulo(s.revisor_id),
        revisadaEn: s.revisada_en,
        ordenGeneradaId: idONulo(s.orden_generada_id),
    };
}

class NuevaAtencionService implements NuevaAtencionPort {
    async solicitar(ordenCanceladaId: string, descripcion: string): Promise<ResultadoSolicitud> {
        const respuesta = await apiClient.post<SolicitudNuevaAtencionApi>(
            `/ordenes/${ordenCanceladaId}/nueva-atencion`,
            { descripcion: descripcion.trim() }
        );
        return { solicitud: mapSolicitudApi(respuesta.data), creada: respuesta.status === 201 };
    }

    async listar(
        filtros: FiltrosSolicitudes,
        pagina: { limit: number; offset: number }
    ): Promise<PaginaSolicitudes> {
        const params: Record<string, string | number> = { limit: pagina.limit, offset: pagina.offset };
        if (filtros.situacion) params.situacion = filtros.situacion;
        if (filtros.ordenCanceladaId) params.orden_cancelada_id = Number(filtros.ordenCanceladaId);
        if (filtros.ordenGeneradaId) params.orden_generada_id = Number(filtros.ordenGeneradaId);
        const { data } = await apiClient.get<PaginaSolicitudesApi>('/ordenes/nuevas-atenciones', { params });
        return { ...data, items: data.items.map(mapSolicitudApi) };
    }

    async revisar(
        solicitudId: string,
        decision: DecisionRevision,
        respuesta: string
    ): Promise<SolicitudNuevaAtencion> {
        const { data } = await apiClient.post<SolicitudNuevaAtencionApi>(
            `/ordenes/nuevas-atenciones/${solicitudId}/revision`,
            { decision, respuesta: respuesta.trim() }
        );
        if (
            !data ||
            data.situacion === 'pendiente' ||
            !data.respuesta ||
            data.revisor_id === null ||
            !data.revisada_en
        ) {
            throw new RespuestaIncompletaError('La respuesta no incluyó la revisión registrada.');
        }
        return mapSolicitudApi(data);
    }

    async generarOrden(solicitudId: string): Promise<ResultadoGeneracion> {
        const respuesta = await apiClient.post<GeneracionApi>(
            `/ordenes/nuevas-atenciones/${solicitudId}/orden`,
            {}
        );
        const { solicitud, orden } = respuesta.data ?? ({} as Partial<GeneracionApi>);
        if (!solicitud || !orden || solicitud.orden_generada_id !== orden.orden_id) {
            throw new RespuestaIncompletaError('La respuesta no incluyó la orden vinculada a la solicitud.');
        }
        return {
            solicitud: mapSolicitudApi(solicitud),
            orden: mapOrdenApi(orden),
            creada: respuesta.status === 201,
        };
    }

    async obtener(solicitudId: string): Promise<SolicitudNuevaAtencion> {
        const { data } = await apiClient.get<SolicitudNuevaAtencionApi>(
            `/ordenes/nuevas-atenciones/${solicitudId}`
        );
        return mapSolicitudApi(data);
    }
}

export const nuevaAtencionService = new NuevaAtencionService();
