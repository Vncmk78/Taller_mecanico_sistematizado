/**
 * Solicitud de cancelación que un Cliente registra sobre una orden y que el
 * Administrador debe revisar. La orden conserva su estado hasta que la
 * solicitud se confirma (contrato `SolicitudCancelacionRespuesta`).
 */
export type EstadoSolicitudCancelacion = 'pendiente' | 'confirmada';

export interface SolicitudCancelacion {
    /** Identificador de la solicitud (`solicitud_id`). */
    id: string;
    ordenId: string;
    clienteUsuarioId: string;
    /** Estado de la orden en el momento de solicitar la cancelación. */
    estadoAlSolicitar: number;
    motivo: string;
    estado: EstadoSolicitudCancelacion;
    solicitadaEn: string;
    administradorId: string | null;
    confirmadaEn: string | null;
}
