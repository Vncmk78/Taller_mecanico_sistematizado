import { describe, expect, it } from 'vitest';
import type { Repuesto } from '@/domain/entities/Repuesto';
import { getStockStatus, getStockStatusLabel, STOCK_STATUS_OPTIONS } from './stockStatus';

function repuesto(overrides: Partial<Repuesto> = {}): Repuesto {
    return {
        repuestoId: 1,
        nombre: 'Filtro de aceite',
        proveedorId: 1,
        proveedorNombre: 'Repuestos del Sur',
        proveedorTipoDistribuidor: 'oficial',
        stock: 10,
        umbralParticular: null,
        umbralEfectivo: 5,
        bajoUmbral: false,
        ...overrides,
    };
}

describe('getStockStatus: clasificación del stock', () => {
    it('marca sin stock cuando no quedan unidades', () => {
        expect(getStockStatus(repuesto({ stock: 0 })).key).toBe('sin_stock');
        expect(getStockStatus(repuesto({ stock: -3 })).key).toBe('sin_stock');
    });

    it('marca crítico cuando el stock es la mitad o menos del umbral', () => {
        expect(getStockStatus(repuesto({ stock: 5, umbralEfectivo: 10 })).key).toBe('critico');
        expect(getStockStatus(repuesto({ stock: 1, umbralEfectivo: 10 })).key).toBe('critico');
    });

    it('marca bajo cuando está por debajo del umbral pero sobre la mitad', () => {
        expect(getStockStatus(repuesto({ stock: 6, umbralEfectivo: 10 })).key).toBe('bajo');
        expect(getStockStatus(repuesto({ stock: 9, umbralEfectivo: 10 })).key).toBe('bajo');
    });

    it('marca normal cuando alcanza el umbral o lo supera', () => {
        // El backend considera bajo_umbral solo con stock < umbral (estricto).
        expect(getStockStatus(repuesto({ stock: 10, umbralEfectivo: 10 })).key).toBe('normal');
        expect(getStockStatus(repuesto({ stock: 40, umbralEfectivo: 10 })).key).toBe('normal');
    });

    it('marca normal cuando hay stock pero no hay umbral configurado', () => {
        expect(
            getStockStatus(repuesto({ stock: 3, umbralEfectivo: null, umbralParticular: null })).key
        ).toBe('normal');
        expect(getStockStatus(repuesto({ stock: 3, umbralEfectivo: 0 })).key).toBe('normal');
    });

    it('prefiere el umbral efectivo sobre el particular', () => {
        expect(
            getStockStatus(repuesto({ stock: 10, umbralEfectivo: 20, umbralParticular: 1 })).key
        ).toBe('critico');
    });

    it('usa el umbral particular si no hay efectivo', () => {
        expect(
            getStockStatus(repuesto({ stock: 2, umbralEfectivo: null, umbralParticular: 10 })).key
        ).toBe('critico');
    });
});

describe('STOCK_STATUS_OPTIONS: catálogo del filtro', () => {
    it('expone los cuatro estados en orden de gravedad con sus etiquetas', () => {
        expect(STOCK_STATUS_OPTIONS).toEqual([
            { key: 'sin_stock', label: 'Sin stock' },
            { key: 'critico', label: 'Crítico' },
            { key: 'bajo', label: 'Bajo' },
            { key: 'normal', label: 'Normal' },
        ]);
    });

    it('getStockStatusLabel devuelve la etiqueta legible de cada estado', () => {
        expect(getStockStatusLabel('sin_stock')).toBe('Sin stock');
        expect(getStockStatusLabel('critico')).toBe('Crítico');
        expect(getStockStatusLabel('bajo')).toBe('Bajo');
        expect(getStockStatusLabel('normal')).toBe('Normal');
    });
});
