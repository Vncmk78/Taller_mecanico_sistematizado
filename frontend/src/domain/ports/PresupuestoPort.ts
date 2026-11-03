import type {
    DecisionCliente,
    Presupuesto,
    ResultadoDecision,
    VersionPresupuesto,
} from '../entities/Presupuesto';

export interface ItemPresupuestoInput {
    tipo: 'repuesto' | 'mano_de_obra';
    descripcion: string;
    cantidad: number;
    precioUnitario: number;
    repuestoId?: string | null;
}

export interface ResultadoEnvio {
    presupuesto: Presupuesto;
    efectoEnOrden: string | null;
    decisionId: string | null;
    aplicacionConfirmada: boolean;
}

export interface PresupuestoPort {
    /**
     * Presupuesto visible de una orden del cliente (versiones enviadas). `null`
     * cuando la orden todavía no tiene un presupuesto enviado.
     */
    getByOrder(ordenId: string): Promise<Presupuesto | null>;
    /** Detalle de un presupuesto con sus versiones e ítems (404 si es ajeno). */
    getById(presupuestoId: string): Promise<Presupuesto>;
    /** Crea el presupuesto de una orden con su versión 1 en borrador. */
    create(ordenId: string, items: ItemPresupuestoInput[]): Promise<Presupuesto>;
    /** Crea la versión siguiente (copia la última o usa `items`). */
    createVersion(
        presupuestoId: string,
        options?: { items?: ItemPresupuestoInput[]; copiarDe?: number }
    ): Promise<Presupuesto>;
    /** Reemplaza los ítems de una versión en borrador. */
    replaceItems(
        presupuestoId: string,
        numero: number,
        items: ItemPresupuestoInput[]
    ): Promise<VersionPresupuesto>;
    /** Envía la versión al cliente (queda congelada). */
    send(presupuestoId: string, numero: number): Promise<ResultadoEnvio>;
    /**
     * Aprobar o rechazar la versión enviada. Todo rechazo exige `motivo`; antes
     * de la primera aprobación exige `confirmarCancelacion`.
     */
    decidir(
        presupuestoId: string,
        numero: number,
        decision: DecisionCliente,
        motivo?: string,
        confirmarCancelacion?: boolean
    ): Promise<ResultadoDecision>;
}
