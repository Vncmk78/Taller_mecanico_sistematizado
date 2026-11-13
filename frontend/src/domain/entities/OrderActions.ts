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

// El cliente solicita la cancelación; el Administrador la confirma desde la
// bandeja de cancelaciones pendientes (/admin/cancelaciones), donde solo
// aparecen órdenes con solicitud registrada. No se ofrece como acción de la
// orden: el backend responde 409 si no existe una solicitud que confirmar.
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

    // Mismo control y mismo endpoint (PUT /ordenes/{id}/mecanico) para asignar
    // y reasignar. MS2 decide el efecto: la primera asignación de una orden
    // Recibida pasa a Esperando diagnóstico; una reasignación conserva el
    // estado. Las órdenes terminales no admiten cambios de responsable, y la
    // capacidad la valida MS2 al registrar la operación.
    if (order.estadoCodigo !== ENTREGADO && order.estadoCodigo !== CANCELADO) {
        const reasignar = order.mecanicoActualId !== null;
        if (reasignar || order.estadoCodigo === 1) {
            acciones.push({
                id: 'asignar_mecanico',
                etiqueta: reasignar ? 'Reasignar mecánico' : 'Asignar mecánico',
                destinos: [],
                requiereMotivo: false,
                habilitada: true,
            });
        }
    }

    // La cancelación no se ofrece aquí: se confirma desde la bandeja de
    // cancelaciones pendientes, que solo lista solicitudes reales.

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

/**
 * El Administrador puede registrar la devolución física del vehículo de una
 * orden Cancelada que aún no la tiene. Recibe todos los roles de la cuenta:
 * una cuenta multirrol con Administrador también puede. Si la respuesta no
 * informó la devolución (`undefined`), no se ofrece: no se sabe si ya existe.
 * MS2 conserva la autoridad final (por ejemplo, el 409 de un ingreso
 * compartido con otra orden activa).
 */
export function puedeRegistrarDevolucion(order: Order, roles: readonly RolOrden[]): boolean {
    return (
        roles.includes('administrador') &&
        order.estadoCodigo === CANCELADO &&
        order.devueltoEn === null
    );
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
            etiqueta: 'Solicitar cancelación',
            destinos: [],
            requiereMotivo: true,
            habilitada: true,
        });
    }

    return acciones;
}
