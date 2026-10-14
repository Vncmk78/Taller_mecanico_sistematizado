import { AVANCES_MECANICO, type Order } from './Order';

// Catálogo centralizado de acciones sobre una orden según su estado actual y el
// rol de quien la mira. Es la única fuente de verdad que consumen los tres
// portales (mecánico, administrador y cliente) para decidir qué controles
// ofrecer. El backend conserva la autoridad final sobre permisos, transiciones
// y precondiciones; este módulo solo evita ofrecer acciones imposibles o
// prohibidas desde la interfaz.
export type RolOrden = 'administrador' | 'mecanico' | 'cliente';

export interface ActorOrden {
    rol: RolOrden;
    /** usuario_id de MS1 del actor; sirve para verificar asignación del mecánico. */
    userId: string | null;
}

export type AccionOrdenId =
    | 'avanzar_estado'
    | 'asignar_mecanico'
    | 'cancelar'
    | 'registrar_entrega'
    | 'decidir_presupuesto';

export interface AccionOrden {
    id: AccionOrdenId;
    etiqueta: string;
    /** Estados destino posibles. Vacío cuando la acción no cambia el estado (p. ej. asignar). */
    destinos: number[];
    /** Exige un motivo/observación no vacío al ejecutar. */
    requiereMotivo: boolean;
    habilitada: boolean;
    motivoBloqueo?: string;
}

/** Destinos de avance que el mecánico puede ejecutar en un estado dado. */
export function destinosAvanceMecanico(estadoCodigo: number): number[] {
    return AVANCES_MECANICO[estadoCodigo] ?? [];
}

// Orden cancelable por su responsable (cliente) o por el taller (administrador):
// mientras no haya avanzado a un estado terminal ni esté en manos del mecánico.
const ESTADOS_CANCELABLES = new Set([1, 2, 3]);

const CANCELADO = 8;
const ENTREGADO = 7;

/**
 * Catálogo de acciones disponibles para un actor sobre una orden concreta.
 *
 * Es una función pura: no consulta red ni estado global, de modo que los tres
 * portales comparten exactamente las mismas reglas y son fáciles de probar.
 */
export function accionesDisponibles(order: Order, actor: ActorOrden): AccionOrden[] {
    switch (actor.rol) {
        case 'mecanico':
            return accionesMecanico(order, actor);
        case 'administrador':
            return accionesAdministrador(order);
        case 'cliente':
            return accionesCliente(order);
    }
}

function accionesMecanico(order: Order, actor: ActorOrden): AccionOrden[] {
    const destinos = destinosAvanceMecanico(order.estadoCodigo);
    if (destinos.length === 0) return [];

    const asignada =
        order.mecanicoActualId !== null && order.mecanicoActualId === actor.userId;

    return [
        {
            id: 'avanzar_estado',
            etiqueta: 'Avanzar estado',
            destinos,
            requiereMotivo: false,
            habilitada: asignada,
            motivoBloqueo: asignada
                ? undefined
                : 'Solo el mecánico asignado puede actualizar esta orden.',
        },
    ];
}

function accionesAdministrador(order: Order): AccionOrden[] {
    const acciones: AccionOrden[] = [];

    // La primera asignación saca la orden de "Recibido" (1 -> 2).
    if (order.estadoCodigo === 1) {
        acciones.push({
            id: 'asignar_mecanico',
            etiqueta: 'Asignar mecánico',
            destinos: [],
            requiereMotivo: false,
            habilitada: true,
        });
    }

    if (ESTADOS_CANCELABLES.has(order.estadoCodigo)) {
        acciones.push({
            id: 'cancelar',
            etiqueta: 'Cancelar orden',
            destinos: [CANCELADO],
            requiereMotivo: true,
            habilitada: true,
        });
    }

    // La entrega física cierra el ciclo normal (6 -> 7).
    if (order.estadoCodigo === 6) {
        acciones.push({
            id: 'registrar_entrega',
            etiqueta: 'Registrar entrega',
            destinos: [ENTREGADO],
            requiereMotivo: false,
            habilitada: true,
        });
    }

    return acciones;
}

function accionesCliente(order: Order): AccionOrden[] {
    const acciones: AccionOrden[] = [];

    if (order.estadoCodigo === 3) {
        acciones.push({
            id: 'decidir_presupuesto',
            etiqueta: 'Gestionar presupuesto',
            destinos: [],
            requiereMotivo: false,
            habilitada: true,
        });
    }

    if (ESTADOS_CANCELABLES.has(order.estadoCodigo)) {
        acciones.push({
            id: 'cancelar',
            etiqueta: 'Cancelar solicitud',
            destinos: [CANCELADO],
            requiereMotivo: true,
            habilitada: true,
        });
    }

    return acciones;
}
