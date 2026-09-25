import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { Order } from '@/domain/entities/Order';
import { useOrderListFilters } from './useOrderListFilters';

const orders: Order[] = Array.from({ length: 8 }, (_, i) => ({
    id: `O-${i + 1}`,
    vehicleId: '1',
    ingresoId: i + 1,
    // Pares en "Recibido" (1), impares en "En reparación" (5).
    estadoCodigo: i % 2 === 0 ? 1 : 5,
    mecanicoActualId: null,
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:00:00',
    actualizadoEn: `2026-09-${String((i % 9) + 1).padStart(2, '0')}T12:00:00`,
    patente: `PT-${i}`,
}));

const haystack = (o: Order) => `${o.id} ${o.patente ?? ''}`;

describe('useOrderListFilters: filtros y paginación del listado', () => {
    it('filtra por estado y resetea la página al cambiar el filtro', () => {
        const { result } = renderHook(() => useOrderListFilters(orders, haystack));

        act(() => result.current.setPage(2));
        expect(result.current.page).toBe(2);

        act(() => result.current.setEstadoCodigo(5));
        expect(result.current.page).toBe(1);
        expect(result.current.filteredOrders).toHaveLength(4);
        expect(result.current.pagedOrders.every((o) => o.estadoCodigo === 5)).toBe(true);
    });

    it('busca por texto en los campos entregados', () => {
        const { result } = renderHook(() => useOrderListFilters(orders, haystack));

        act(() => result.current.setSearch('PT-3'));
        expect(result.current.filteredOrders.map((o) => o.id)).toEqual(['O-4']);
    });

    it('ordena por actualización más reciente por defecto', () => {
        const { result } = renderHook(() => useOrderListFilters(orders, haystack));

        expect(result.current.filteredOrders[0].id).toBe('O-8');
        expect(result.current.filteredOrders[result.current.total - 1].id).toBe('O-1');
        expect(result.current.pagedOrders).toHaveLength(6);
        expect(result.current.rangeEnd).toBe(6);
    });
});