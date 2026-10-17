// Presupuesto de una orden (MS3). Espejo del contrato de la API Gateway
// (PresupuestoResumen/PresupuestoDetalle). El backend serializa el dinero como
// texto ("38990.00") para no perder precisión; el dominio del frontend lo
// normaliza a number y deja el formato $ al presentador.

export type EstadoVersionPresupuesto = 'borrador' | 'enviada' | 'aprobada' | 'rechazada';
export type TipoItemPresupuesto = 'repuesto' | 'mano_de_obra';
export type DecisionCliente = 'aprobado' | 'rechazado';

// Efecto que la decisión provoca en el estado de la orden (MS2).
export type EfectoEnOrden =
    | 'esperando_aprobacion'
    | 'en_reparacion'
    | 'esperando_repuestos'
    | 'cancelado';

export const ESTADO_VERSION_LABEL: Record<EstadoVersionPresupuesto, string> = {
    borrador: 'Borrador',
    enviada: 'Pendiente de su decisión',
    aprobada: 'Aprobado',
    rechazada: 'Rechazado',
};

export function estadoVersionLabel(estado: EstadoVersionPresupuesto): string {
    return ESTADO_VERSION_LABEL[estado] ?? estado;
}

export const TIPO_ITEM_LABEL: Record<TipoItemPresupuesto, string> = {
    repuesto: 'Repuesto',
    mano_de_obra: 'Mano de obra',
};

export interface ItemPresupuesto {
    id: string;
    tipo: TipoItemPresupuesto;
    descripcion: string;
    cantidad: number;
    precioUnitario: number;
    subtotal: number;
    repuestoId: string | null;
    /** Procedencia visible para el cliente: nombre del repuesto y su distribuidor. */
    repuestoNombre?: string;
    proveedorNombre?: string;
}

export interface DecisionPresupuesto {
    id: string;
    decision: DecisionCliente;
    fecha: string;
    motivo?: string;
}

export interface VersionPresupuesto {
    numero: number;
    estado: EstadoVersionPresupuesto;
    esModificacion: boolean;
    creadoEn: string;
    enviadoEn?: string;
    bloqueadaEn?: string;
    total: number;
    items: ItemPresupuesto[];
    decision?: DecisionPresupuesto;
}

export interface Presupuesto {
    id: string;
    orderId: string;
    creadoEn: string;
    cantidadVersiones: number;
    ultimaVersion: number;
    estadoUltimaVersion: EstadoVersionPresupuesto;
    totalUltimaVersion: number;
    /** Número de la última versión aprobada (alcance autorizado), si existe. */
    versionVigente: number | null;
    /**
     * Versiones visibles para el cliente (solo las enviadas). El listado no las
     * trae; el detalle sí. Puede venir vacío mientras se resuelve el detalle.
     */
    versiones: VersionPresupuesto[];
}

export interface ResultadoDecision {
    presupuesto: Presupuesto;
    efectoEnOrden: EfectoEnOrden | null;
    decisionId: string | null;
    /** true si la transición inicial quedó aplicada en la orden (MS2). */
    aplicacionConfirmada: boolean;
}

/** Versión enviada que aún espera la decisión del cliente (la más reciente). */
export function versionPendiente(presupuesto: Presupuesto): VersionPresupuesto | undefined {
    return [...presupuesto.versiones]
        .filter((version) => version.estado === 'enviada' && !version.decision)
        .sort((a, b) => b.numero - a.numero)[0];
}

/** Versión aprobada vigente (alcance autorizado) o la última enviada si aún no hay ninguna. */
export function versionVigente(presupuesto: Presupuesto): VersionPresupuesto | undefined {
    const aprobada = presupuesto.versiones.find(
        (version) => version.numero === presupuesto.versionVigente
    );
    if (aprobada) return aprobada;
    return [...presupuesto.versiones].sort((a, b) => b.numero - a.numero)[0];
}

/**
 * true cuando todavía no hay ninguna versión aprobada: rechazar entonces rechaza
 * el servicio completo y MS3 exige confirmar la cancelación de la orden.
 */
export function rechazoCancelaServicio(presupuesto: Presupuesto): boolean {
    return presupuesto.versionVigente === null;
}
