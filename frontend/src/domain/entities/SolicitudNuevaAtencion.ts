// Solicitud de nueva atención después de una cancelación (Sistematización 4.9;
// contrato-web-bloques-3-4.md, Entrega B). No reserva hora, no crea una orden
// ni consume cupo: el Administrador la revisa y, si corresponde, crea una orden
// distinta. Su situación de revisión es independiente de los estados de orden.

export type SituacionSolicitud = 'pendiente' | 'aceptada' | 'rechazada';

export const SITUACIONES_SOLICITUD: Record<SituacionSolicitud, string> = {
    pendiente: 'Pendiente de revisión',
    aceptada: 'Aceptada',
    rechazada: 'Rechazada',
};

export interface SolicitudNuevaAtencion {
    id: string;
    ordenCanceladaId: string;
    vehiculoId: string;
    clienteUsuarioId: string;
    descripcion: string;
    /** Fecha y hora registradas por el servidor (ISO 8601). */
    solicitadaEn: string;
    situacion: SituacionSolicitud;
    /** Respuesta administrativa; null mientras esté pendiente. */
    respuesta: string | null;
    revisorId: string | null;
    revisadaEn: string | null;
    /** Orden creada por el Administrador a partir de esta solicitud (Entrega C). */
    ordenGeneradaId: string | null;
}

export interface PaginaSolicitudes {
    items: SolicitudNuevaAtencion[];
    total: number;
    limit: number;
    offset: number;
}

export interface FiltrosSolicitudes {
    situacion?: SituacionSolicitud;
    ordenCanceladaId?: string;
    ordenGeneradaId?: string;
}

/** Máximo de caracteres de la descripción, ya recortada (lo valida también MS2). */
export const DESCRIPCION_SOLICITUD_MAX = 2000;

/**
 * Valida la descripción como lo hará MS2: se recortan los espacios exteriores
 * y el texto resultante no puede quedar vacío ni superar 2000 caracteres.
 * Devuelve el mensaje de error o null si es válida.
 */
export function validarDescripcionSolicitud(texto: string): string | null {
    const recortado = texto.trim();
    if (recortado === '') return 'Describa lo que necesita que revise el taller.';
    if (recortado.length > DESCRIPCION_SOLICITUD_MAX) {
        return `La descripción no puede superar ${DESCRIPCION_SOLICITUD_MAX} caracteres (tiene ${recortado.length}).`;
    }
    return null;
}

/**
 * Una solicitud pendiente o aceptada impide otra sobre la misma orden
 * cancelada (también si la aceptada ya generó una orden). Solo orienta la
 * interfaz: MS2 decide y responde 409 si no corresponde.
 */
export function bloqueaNuevaSolicitud(solicitud: SolicitudNuevaAtencion): boolean {
    return solicitud.situacion === 'pendiente' || solicitud.situacion === 'aceptada';
}
