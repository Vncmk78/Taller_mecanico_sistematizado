import { describe, expect, it } from 'vitest';
import {
    mockEvidenciaFrenos,
    mockEvidenciaPresupuesto,
    mockEvidenciasOrden101,
} from '@/infrastructure/mocks/evidence.mock';
import {
    contarPorContexto,
    contextosPresentes,
    evidenciasDelPresupuesto,
    filtrarPorContexto,
    formatBytes,
} from './evidenceDisplay';

describe('formatBytes', () => {
    it('muestra bytes sin decimales', () => {
        expect(formatBytes(512)).toBe('512 B');
    });

    it('escala a KB y MB con separador decimal chileno', () => {
        expect(formatBytes(1024)).toBe('1 KB');
        expect(formatBytes(482133)).toBe('470,8 KB');
        expect(formatBytes(6 * 1024 * 1024)).toBe('6 MB');
    });

    it('tolera valores no válidos', () => {
        expect(formatBytes(0)).toBe('0 B');
        expect(formatBytes(-10)).toBe('0 B');
    });
});

describe('contextosPresentes', () => {
    it('devuelve solo los contextos de la lista, en el orden oficial', () => {
        expect(contextosPresentes(mockEvidenciasOrden101)).toEqual(['diagnostico', 'resultado_final']);
        expect(contextosPresentes([])).toEqual([]);
        expect(contextosPresentes([mockEvidenciaPresupuesto])).toEqual(['presupuesto']);
    });
});

describe('contarPorContexto', () => {
    it('cuenta por contexto dejando en 0 los ausentes', () => {
        const conteo = contarPorContexto([...mockEvidenciasOrden101, mockEvidenciaPresupuesto]);
        expect(conteo).toEqual({
            diagnostico: 1,
            presupuesto: 1,
            reparacion: 0,
            resultado_final: 2,
        });
    });

    it('una lista vacía queda en cero para todos los contextos', () => {
        expect(contarPorContexto([])).toEqual({
            diagnostico: 0,
            presupuesto: 0,
            reparacion: 0,
            resultado_final: 0,
        });
    });
});

describe('filtrarPorContexto', () => {
    it('devuelve la lista completa con "todos"', () => {
        expect(filtrarPorContexto(mockEvidenciasOrden101, 'todos')).toEqual(mockEvidenciasOrden101);
    });

    it('acota al contexto seleccionado', () => {
        const filtradas = filtrarPorContexto(mockEvidenciasOrden101, 'resultado_final');
        expect(filtradas).toHaveLength(2);
        expect(filtradas.every((evidencia) => evidencia.contexto === 'resultado_final')).toBe(true);
    });

    it('un contexto sin evidencias devuelve una lista vacía', () => {
        expect(filtrarPorContexto([mockEvidenciaFrenos], 'reparacion')).toEqual([]);
    });
});

describe('evidenciasDelPresupuesto', () => {
    it('trae solo la evidencia del contexto presupuesto del presupuesto indicado', () => {
        const lista = [mockEvidenciaFrenos, mockEvidenciaPresupuesto];
        expect(evidenciasDelPresupuesto(lista, '501')).toEqual([mockEvidenciaPresupuesto]);
    });

    it('ignora evidencias de otro presupuesto o de otros contextos', () => {
        expect(evidenciasDelPresupuesto([mockEvidenciaFrenos], '501')).toEqual([]);
        expect(evidenciasDelPresupuesto([mockEvidenciaPresupuesto], '999')).toEqual([]);
    });
});
