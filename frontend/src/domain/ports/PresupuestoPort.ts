import type {
    DecisionCliente,
    Presupuesto,
    ResultadoDecision,
} from '../entities/Presupuesto';

export interface PresupuestoPort {
    /**
     * Presupuesto visible de una orden del cliente (versiones enviadas). `null`
     * cuando la orden todavía no tiene un presupuesto enviado.
     */
    getByOrder(ordenId: string): Promise<Presupuesto | null>;
    /** Detalle de un presupuesto con sus versiones e ítems (404 si es ajeno). */
    getById(presupuestoId: string): Promise<Presupuesto>;
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
