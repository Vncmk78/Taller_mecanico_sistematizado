import { describe, expect, it } from 'vitest';
import { aplicacionPendiente, type Presupuesto, type VersionPresupuesto } from './Presupuesto';

const version = (numero: number, estado: VersionPresupuesto['estado'], extra: Partial<VersionPresupuesto> = {}): VersionPresupuesto => ({
    numero, estado, esModificacion: false, creadoEn: '2026-11-09T10:00:00-03:00', total: 100, items: [], ...extra,
});
const presupuesto = (versiones: VersionPresupuesto[]): Presupuesto => ({
    id: '9', orderId: '101', creadoEn: '', cantidadVersiones: versiones.length, ultimaVersion: versiones.length,
    estadoUltimaVersion: versiones[versiones.length - 1].estado, totalUltimaVersion: 100, versionVigente: null, versiones,
});
const decidida = version(1, 'aprobada', { decision: { id: '77', decision: 'aprobado', fecha: '' } });

describe('aplicacionPendiente', () => {
    it.each([
        ['borrador con orden asignada', [version(1, 'borrador')], 2, null],
        ['envío guardado con orden sin avanzar', [version(1, 'enviada')], 2, { tipo: 'envio', id: '9' }],
        ['envío aplicado', [version(1, 'enviada')], 3, null],
        ['decisión guardada con orden esperando aprobación', [decidida], 3, { tipo: 'decision', id: '77' }],
        ['decisión aplicada', [decidida], 5, null],
        ['decisión de una modificación no es inicial', [decidida, version(2, 'rechazada', { esModificacion: true, decision: { id: '78', decision: 'rechazado', fecha: '' } })], 5, null],
        ['estado de orden desconocido: no supone nada', [version(1, 'enviada')], null, null],
    ] as const)('%s', (_, versiones, estado, esperado) => {
        expect(aplicacionPendiente(presupuesto([...versiones]), estado)).toEqual(esperado);
    });
});
