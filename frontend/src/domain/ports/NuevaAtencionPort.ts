import type { Order } from '../entities/Order';
import type {
    DecisionRevision,
    FiltrosSolicitudes,
    PaginaSolicitudes,
    SolicitudNuevaAtencion,
} from '../entities/SolicitudNuevaAtencion';

export interface ResultadoSolicitud {
    solicitud: SolicitudNuevaAtencion;
    /** true con 201 (solicitud nueva); false con 200 (pendiente idéntica ya existente). */
    creada: boolean;
}

export interface ResultadoGeneracion {
    solicitud: SolicitudNuevaAtencion;
    orden: Order;
    /** true con 201 (orden y vínculo nuevos); false con 200 (vínculo ya existente). */
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
    /**
     * Revisión administrativa de una solicitud pendiente
     * (POST /ordenes/nuevas-atenciones/{id}/revision). Solo envía decisión y
     * respuesta recortada: responsable y fecha los registra MS2. Repetir la
     * misma revisión devuelve la existente; otro contenido responde 409.
     */
    revisar(solicitudId: string, decision: DecisionRevision, respuesta: string): Promise<SolicitudNuevaAtencion>;
    /**
     * Genera la orden de una solicitud aceptada (POST
     * /ordenes/nuevas-atenciones/{id}/orden, body {}). MS2 crea la orden y el
     * vínculo en una transacción; si ya existía, devuelve la misma asociación.
     */
    generarOrden(solicitudId: string): Promise<ResultadoGeneracion>;
}
