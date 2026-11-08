import type {
    FiltrosSolicitudes,
    PaginaSolicitudes,
    SolicitudNuevaAtencion,
} from '../entities/SolicitudNuevaAtencion';

export interface ResultadoSolicitud {
    solicitud: SolicitudNuevaAtencion;
    /** true con 201 (solicitud nueva); false con 200 (pendiente idéntica ya existente). */
    creada: boolean;
}

export interface NuevaAtencionPort {
    /**
     * Solicita una nueva atención sobre una orden Cancelada del Cliente
     * propietario (POST /ordenes/{id}/nueva-atencion). Solo envía la
     * descripción recortada: identidad, fecha y situación las decide MS2.
     */
    solicitar(ordenCanceladaId: string, descripcion: string): Promise<ResultadoSolicitud>;
    /**
     * Solicitudes visibles para la cuenta (GET /ordenes/nuevas-atenciones): las
     * propias del Cliente o todas si la cuenta incluye Administrador.
     */
    listar(
        filtros: FiltrosSolicitudes,
        pagina: { limit: number; offset: number }
    ): Promise<PaginaSolicitudes>;
    /** Detalle de una solicitud (GET /ordenes/nuevas-atenciones/{id}). */
    obtener(solicitudId: string): Promise<SolicitudNuevaAtencion>;
}
