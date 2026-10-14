import { describe, expect, it } from 'vitest';
import type { Order } from './Order';
import {
    accionesDisponibles,
    destinosAvanceMecanico,
    type ActorOrden,
} from './OrderActions';

function orden(estadoCodigo: number, mecanicoActualId: string | null = 'm1'): Order {
    return {
        id: '101',
        vehicleId: '1',
        ingresoId: 101,
        estadoCodigo,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
    };
}

const MECANICO: ActorOrden = { rol: 'mecanico', userId: 'm1' };
const ADMIN: ActorOrden = { rol: 'administrador', userId: 'a1' };
const CLIENTE: ActorOrden = { rol: 'cliente', userId: 'c1' };

describe('OrderActions: catálogo centralizado de acciones por estado y rol', () => {
    describe('destinosAvanceMecanico', () => {
        it('devuelve los destinos del catálogo del mecánico', () => {
            expect(destinosAvanceMecanico(2)).toEqual([3]);
            expect(destinosAvanceMecanico(4)).toEqual([5]);
            expect(destinosAvanceMecanico(5)).toEqual([6]);
        });

        it('devuelve lista vacía en estados sin avance', () => {
            expect(destinosAvanceMecanico(1)).toEqual([]);
            expect(destinosAvanceMecanico(3)).toEqual([]);
            expect(destinosAvanceMecanico(6)).toEqual([]);
            expect(destinosAvanceMecanico(7)).toEqual([]);
            expect(destinosAvanceMecanico(8)).toEqual([]);
        });
    });

    describe('mecánico', () => {
        it.each([
            [2, [3]],
            [4, [5]],
            [5, [6]],
        ])('en estado %i ofrece avanzar a %j cuando la orden es suya', (estado, destinos) => {
            const acciones = accionesDisponibles(orden(estado, 'm1'), MECANICO);

            expect(acciones).toHaveLength(1);
            expect(acciones[0]).toMatchObject({
                id: 'avanzar_estado',
                destinos,
                habilitada: true,
            });
        });

        it('marca bloqueada la acción si la orden es de otro mecánico', () => {
            const acciones = accionesDisponibles(orden(5, 'm2'), MECANICO);

            expect(acciones).toHaveLength(1);
            expect(acciones[0].habilitada).toBe(false);
            expect(acciones[0].motivoBloqueo).toMatch(/Solo el mecánico asignado/);
        });

        it('marca bloqueada la acción si la orden no está asignada', () => {
            const acciones = accionesDisponibles(orden(5, null), MECANICO);

            expect(acciones).toHaveLength(1);
            expect(acciones[0].habilitada).toBe(false);
        });

        it('no ofrece acciones en estados sin avance del mecánico', () => {
            expect(accionesDisponibles(orden(1), MECANICO)).toEqual([]);
            expect(accionesDisponibles(orden(3), MECANICO)).toEqual([]);
            expect(accionesDisponibles(orden(6), MECANICO)).toEqual([]);
            expect(accionesDisponibles(orden(7), MECANICO)).toEqual([]);
            expect(accionesDisponibles(orden(8), MECANICO)).toEqual([]);
        });
    });

    describe('administrador', () => {
        it('en estado 1 ofrece asignar mecánico y cancelar', () => {
            const acciones = accionesDisponibles(orden(1), ADMIN);

            expect(acciones.map((a) => a.id)).toEqual(['asignar_mecanico', 'cancelar']);
            expect(acciones[0].destinos).toEqual([]);
            expect(acciones[1]).toMatchObject({ destinos: [8], requiereMotivo: true });
        });

        it.each([2, 3])('en estado %i ofrece solo cancelar', (estado) => {
            const acciones = accionesDisponibles(orden(estado), ADMIN);

            expect(acciones.map((a) => a.id)).toEqual(['cancelar']);
        });

        it('en estado 6 ofrece registrar entrega', () => {
            const acciones = accionesDisponibles(orden(6), ADMIN);

            expect(acciones).toHaveLength(1);
            expect(acciones[0]).toMatchObject({ id: 'registrar_entrega', destinos: [7] });
        });

        it.each([4, 5, 7, 8])('no ofrece acciones en estado %i', (estado) => {
            expect(accionesDisponibles(orden(estado), ADMIN)).toEqual([]);
        });
    });

    describe('cliente', () => {
        it('en estado 3 ofrece gestionar presupuesto y cancelar', () => {
            const acciones = accionesDisponibles(orden(3), CLIENTE);

            expect(acciones.map((a) => a.id)).toEqual(['decidir_presupuesto', 'cancelar']);
            expect(acciones[1]).toMatchObject({ destinos: [8], requiereMotivo: true });
        });

        it.each([1, 2])('en estado %i ofrece solo cancelar', (estado) => {
            const acciones = accionesDisponibles(orden(estado), CLIENTE);

            expect(acciones.map((a) => a.id)).toEqual(['cancelar']);
            expect(acciones[0].etiqueta).toBe('Cancelar solicitud');
        });

        it.each([4, 5, 6, 7, 8])('no ofrece acciones en estado %i', (estado) => {
            expect(accionesDisponibles(orden(estado), CLIENTE)).toEqual([]);
        });
    });

    it('no cambia el rol con el que se evalúa (función pura)', () => {
        const o = orden(5);
        const antes = JSON.stringify(o);

        accionesDisponibles(o, MECANICO);

        expect(JSON.stringify(o)).toBe(antes);
    });
});
