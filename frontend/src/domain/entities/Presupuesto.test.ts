import { describe, expect, it } from 'vitest';
import {
    estadoVersionLabel,
    rechazoCancelaServicio,
    versionPendiente,
    versionVigente,
    type Presupuesto,
} from './Presupuesto';
import { mockPresupuestoPendiente } from '@/infrastructure/mocks/budgets.mock';

describe('Presupuesto: reglas de decisión', () => {
    it('versionPendiente devuelve la versión enviada sin decisión más reciente', () => {
        const presupuesto: Presupuesto = {
            ...mockPresupuestoPendiente,
            versiones: [
                { ...mockPresupuestoPendiente.versiones[0], numero: 1, estado: 'rechazada' },
                { ...mockPresupuestoPendiente.versiones[0], numero: 2, estado: 'enviada' },
                { ...mockPresupuestoPendiente.versiones[0], numero: 3, estado: 'enviada' },
            ],
        };

        expect(versionPendiente(presupuesto)?.numero).toBe(3);
    });

    it('versionPendiente ignora las versiones ya decididas', () => {
        const presupuesto: Presupuesto = {
            ...mockPresupuestoPendiente,
            versiones: [
                {
                    ...mockPresupuestoPendiente.versiones[0],
                    numero: 1,
                    estado: 'enviada',
                    decision: { id: 'd', decision: 'aprobado', fecha: '2026-09-03T10:00:00' },
                },
            ],
        };

        expect(versionPendiente(presupuesto)).toBeUndefined();
    });

    it('versionVigente devuelve la versión aprobada cuyo número es el alcance autorizado', () => {
        const presupuesto: Presupuesto = {
            ...mockPresupuestoPendiente,
            versionVigente: 2,
            versiones: [
                { ...mockPresupuestoPendiente.versiones[0], numero: 1, estado: 'rechazada' },
                { ...mockPresupuestoPendiente.versiones[0], numero: 2, estado: 'aprobada' },
            ],
        };

        expect(versionVigente(presupuesto)?.numero).toBe(2);
    });

    it('sin versión aprobada, versionVigente cae en la última enviada', () => {
        const presupuesto: Presupuesto = { ...mockPresupuestoPendiente, versionVigente: null };

        expect(versionVigente(presupuesto)?.numero).toBe(1);
    });

    it('rechazoCancelaServicio solo es true antes de la primera aprobación', () => {
        expect(rechazoCancelaServicio({ ...mockPresupuestoPendiente, versionVigente: null })).toBe(true);
        expect(rechazoCancelaServicio({ ...mockPresupuestoPendiente, versionVigente: 1 })).toBe(false);
    });

    it('etiqueta los estados de la versión', () => {
        expect(estadoVersionLabel('enviada')).toBe('Pendiente de su decisión');
        expect(estadoVersionLabel('aprobada')).toBe('Aprobado');
    });
});
