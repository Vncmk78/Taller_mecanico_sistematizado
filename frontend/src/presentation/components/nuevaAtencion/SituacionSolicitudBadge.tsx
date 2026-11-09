import {
    SITUACIONES_SOLICITUD,
    type SituacionSolicitud,
} from '@/domain/entities/SolicitudNuevaAtencion';

const estilos: Record<SituacionSolicitud, string> = {
    pendiente: 'bg-status-yellow/15 text-status-yellow border-status-yellow/40',
    aceptada: 'bg-status-green/15 text-status-green border-status-green/40',
    rechazada: 'bg-status-red/15 text-status-red border-status-red/40',
};

/** Situación de revisión de una solicitud tal como la informa el servidor. */
export function SituacionSolicitudBadge({ situacion }: { situacion: SituacionSolicitud }) {
    return (
        <span
            className={`inline-flex items-center rounded-full border text-xs font-semibold px-2.5 py-1 shrink-0 ${estilos[situacion]}`}
        >
            {SITUACIONES_SOLICITUD[situacion]}
        </span>
    );
}
