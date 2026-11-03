import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';
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
const wrapper = ({ children }: PropsWithChildren) => createElement(MemoryRouter, null, children);

function filtrosConUrl(initialEntry: string, urlKeyPrefix = '') {
    return renderHook(() => ({
        filtros: useOrderListFilters(orders, haystack, { syncWithUrl: true, urlKeyPrefix }),
        params: new URLSearchParams(useLocation().search),
    }), {
        wrapper: ({ children }: PropsWithChildren) => createElement(
            MemoryRouter, { initialEntries: [initialEntry] }, children
        ),
    });
}

describe('useOrderListFilters: filtros y paginación del listado', () => {
    it('filtra por estado y resetea la página al cambiar el filtro', () => {
        const { result } = renderHook(() => useOrderListFilters(orders, haystack), { wrapper });

        act(() => result.current.setPage(2));
        expect(result.current.page).toBe(2);

        act(() => result.current.setEstadoCodigo(5));
        expect(result.current.page).toBe(1);
        expect(result.current.filteredOrders).toHaveLength(4);
        expect(result.current.pagedOrders.every((o) => o.estadoCodigo === 5)).toBe(true);
    });

    it('busca por texto en los campos entregados', () => {
        const { result } = renderHook(() => useOrderListFilters(orders, haystack), { wrapper });

        act(() => result.current.setSearch('PT-3'));
        expect(result.current.filteredOrders.map((o) => o.id)).toEqual(['O-4']);
    });

    it('ordena por actualización más reciente por defecto', () => {
        const { result } = renderHook(() => useOrderListFilters(orders, haystack), { wrapper });

        expect(result.current.filteredOrders[0].id).toBe('O-8');
        expect(result.current.filteredOrders[result.current.total - 1].id).toBe('O-1');
        expect(result.current.pagedOrders).toHaveLength(6);
        expect(result.current.rangeEnd).toBe(6);
    });
});

describe('useOrderListFilters: actualización conjunta de URL', () => {
    it('cambia búsqueda y página juntos conservando el estado y parámetros ajenos', () => {
        const { result } = filtrosConUrl('/?page=2&estado=5&vista=resumen');
        act(() => result.current.filtros.setSearch('PT-3'));
        expect(result.current.filtros.search).toBe('PT-3');
        expect(result.current.filtros.page).toBe(1);
        expect(result.current.filtros.filteredOrders.map(o => o.id)).toEqual(['O-4']);
        expect(result.current.params.get('q')).toBe('PT-3');
        expect(result.current.params.has('page')).toBe(false);
        expect(result.current.params.get('estado')).toBe('5');
        expect(result.current.params.get('vista')).toBe('resumen');
    });

    it('cambia estado y página juntos conservando la búsqueda', () => {
        const { result } = filtrosConUrl('/?q=PT&page=2');
        act(() => result.current.filtros.setEstadoCodigo(5));
        expect(result.current.filtros.estadoCodigo).toBe(5);
        expect(result.current.filtros.filteredOrders).toHaveLength(4);
        expect(result.current.params.get('estado')).toBe('5');
        expect(result.current.params.get('q')).toBe('PT');
        expect(result.current.params.has('page')).toBe(false);
    });

    it('cambia tamaño de página y reinicia la página sin perder filtros', () => {
        const { result } = filtrosConUrl('/?q=PT&page=2');
        act(() => result.current.filtros.setPageSize(12));
        expect(result.current.filtros.pageSize).toBe(12);
        expect(result.current.params.get('pageSize')).toBe('12');
        expect(result.current.params.get('q')).toBe('PT');
        expect(result.current.params.has('page')).toBe(false);
    });

    it('limpia todos los parámetros del listado con prefijo sin borrar los ajenos', () => {
        const { result } = filtrosConUrl(
            '/?orden-q=PT&orden-estado=5&orden-page=2&orden-pageSize=12&vista=resumen', 'orden-'
        );
        act(() => result.current.filtros.resetFilters());
        expect(result.current.filtros.search).toBe('');
        expect(result.current.filtros.estadoCodigo).toBe('all');
        expect(result.current.filtros.pageSize).toBe(6);
        expect([...result.current.params.entries()]).toEqual([['vista', 'resumen']]);
    });

    it('mantiene la persistencia local entre montajes dentro de una misma sesión', () => {
        const primera = renderHook(() => useOrderListFilters(orders, haystack), { wrapper });
        act(() => primera.result.current.setSearch('PT-3'));
        primera.unmount();
        const segunda = renderHook(() => useOrderListFilters(orders, haystack), { wrapper });
        expect(segunda.result.current.search).toBe('PT-3');
        expect(segunda.result.current.filteredOrders.map(o => o.id)).toEqual(['O-4']);
    });
});
