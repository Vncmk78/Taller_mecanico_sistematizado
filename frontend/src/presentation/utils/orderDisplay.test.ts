import { describe, expect, it } from 'vitest';
import { formatDate, formatDateTime } from './orderDisplay';

// La Gateway devuelve las fechas con offset -03:00 (gateway/contratos/ordenes.py
// usa datetime con zona). Estas pruebas fijan que ese offset se interprete bien
// y no se aplique dos veces. La zona horaria de Vitest está fijada en
// America/Santiago (vite.config.ts), así que el texto esperado es estable.
describe('orderDisplay: fechas con offset de la Gateway', () => {
    it('interpreta el offset -03:00 como hora de Chile, no como UTC', () => {
        expect(formatDateTime('2026-09-28T10:30:00-03:00')).toBe('28 sept 2026, 10:30 a. m.');
    });

    it('produce el mismo texto para el instante UTC equivalente', () => {
        // 10:30 en Chile son las 13:30 UTC. Si el offset se ignorara o se
        // sumara dos veces, los dos strings diferirían en tres horas.
        expect(formatDateTime('2026-09-28T13:30:00.000Z')).toBe(formatDateTime('2026-09-28T10:30:00-03:00'));
    });

    it('formatea la fecha sin la hora para las vistas de solo día', () => {
        expect(formatDate('2026-09-28T10:30:00-03:00')).toBe('28 sept 2026');
    });

    it('devuelve el string original si la fecha no es interpretable', () => {
        // Ante un dato corrupto se muestra lo que llegó, en vez de "Invalid Date".
        expect(formatDateTime('no-es-una-fecha')).toBe('no-es-una-fecha');
        expect(formatDate('no-es-una-fecha')).toBe('no-es-una-fecha');
    });
});
