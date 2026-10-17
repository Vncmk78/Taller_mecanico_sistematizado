import { describe, expect, it } from 'vitest';
import { AVANCES_MECANICO, ESTADOS_ORDEN, ordenStatusLabel } from './Order';

/**
 * Pares que `validar_transicion` acepta en MS2, transcritos de
 * `backend/services/ms2_taller/domain/transiciones_orden.py:70-111`. La función
 * valida el par (estado_actual, estado_destino) e ignora el evento, así que
 * el servicio excluye del PATCH la asignación inicial y las dos ramas de
 * aprobación, que requieren operaciones específicas. Los pares restantes
 * siguen disponibles y algunos tienen precondiciones funcionales pendientes.
 */
const PARES_ACEPTADOS_POR_MS2: ReadonlyArray<readonly [number, number]> = [
    [2, 3],
    [4, 5],
    [5, 6],
    [6, 7],
    [3, 8],
    [1, 8],
    [2, 8],
];

/** Estados sin ninguna transición para el mecánico, con el motivo. */
const ESTADOS_SIN_AVANCE_DEL_MECANICO: Record<number, string> = {
    1: 'la primera asignación la realiza el administrador mediante la operación específica',
    3: 'la aprobación del presupuesto la gestiona el cliente',
    6: 'la entrega física la gestiona el administrador',
    7: 'es terminal (Entregado)',
    8: 'es terminal (Cancelado)',
};

describe('AVANCES_MECANICO: transiciones que la vista del mecánico ofrece', () => {
    it('excluye los pares reservados a las operaciones específicas de MS2', () => {
        const ofrecidos = Object.entries(AVANCES_MECANICO).flatMap(([origen, destinos]) =>
            destinos.map((destino): readonly [number, number] => [Number(origen), destino])
        );

        // Esta comprobación acota pares estructurales y operaciones reservadas.
        // No acredita las precondiciones funcionales aún pendientes.
        for (const par of ofrecidos) {
            expect(PARES_ACEPTADOS_POR_MS2).toContainEqual(par);
        }
    });

    it('ofrece los tres avances conservados sin sustituir la asignación administrativa', () => {
        expect(AVANCES_MECANICO).toEqual({ 2: [3], 4: [5], 5: [6] });
    });

    it('no ofrece avance en los estados que dependen del cliente, el admin o son terminales', () => {
        for (const [estado, motivo] of Object.entries(ESTADOS_SIN_AVANCE_DEL_MECANICO)) {
            expect(
                AVANCES_MECANICO[Number(estado)],
                `el estado ${estado} (${motivo}) no debe ofrecer avances`
            ).toBeUndefined();
        }
    });

    it('los ocho estados del catálogo están deciding entre avance o ausencia de avance', () => {
        // Si MS2 agrega un estado 9, este test obliga a decidir explícitamente si
        // el mecánico puede avanzarlo o si queda en el bloque de cerradas.
        const estadosDelCatalogo = Object.keys(ESTADOS_ORDEN).map(Number);
        const cubiertos = new Set([
            ...Object.keys(AVANCES_MECANICO).map(Number),
            ...Object.keys(ESTADOS_SIN_AVANCE_DEL_MECANICO).map(Number),
        ]);

        expect([...estadosDelCatalogo].sort((a, b) => a - b)).toEqual([...cubiertos].sort((a, b) => a - b));
    });

    it('todo destino ofrecido tiene etiqueta en el catálogo, para no renderizar "Estado 99"', () => {
        for (const destinos of Object.values(AVANCES_MECANICO)) {
            for (const destino of destinos) {
                expect(ESTADOS_ORDEN[destino]).toBeDefined();
            }
        }
    });
});

describe('ordenStatusLabel', () => {
    it('traduce los ocho estados del catálogo', () => {
        expect(ordenStatusLabel(1)).toBe('Recibido');
        expect(ordenStatusLabel(5)).toBe('En reparación');
        expect(ordenStatusLabel(7)).toBe('Entregado');
        expect(ordenStatusLabel(8)).toBe('Cancelado');
    });

    it('degrada a "Estado N" cuando el backend manda un código fuera del catálogo', () => {
        expect(ordenStatusLabel(99)).toBe('Estado 99');
    });
});
