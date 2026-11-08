import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import type { User } from '@/domain/entities/User';
import { hasAnyRole } from '@/presentation/utils/roleVisibility';

export const RUTA_SOLICITUDES_CLIENTE = '/client/nuevas-atenciones';

/**
 * Detalle de una orden relacionada con la solicitud (antecedente o generada).
 * Las propias se abren en el portal del Cliente; una cuenta con Administrador
 * que mira la solicitud de otro cliente usa el detalle administrativo. MS2
 * vuelve a comprobar el acceso en cada caso.
 */
export function rutaOrdenDeSolicitud(
    solicitud: SolicitudNuevaAtencion,
    ordenId: string,
    user: User | null | undefined
): string {
    const propia = user?.id === solicitud.clienteUsuarioId;
    return !propia && hasAnyRole(user, 'administrador')
        ? `/admin/ordenes/${ordenId}`
        : `/client/ordenes/${ordenId}`;
}
