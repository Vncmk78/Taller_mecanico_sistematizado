import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DEFAULT_PAGE_SIZE, PAGE_SIZES } from '@/presentation/constants/pagination';
import { useClientPagination } from './useClientPagination';

const items = Array.from({ length: 15 }, (_, i) => `item-${i + 1}`);

describe('useClientPagination', () => {
    it('usa 6/12/24 y recorta la colección a la página visible', () => {
        const { result } = renderHook(() => useClientPagination(items));

        expect(PAGE_SIZES).toEqual([6, 12, 24]);
        expect(DEFAULT_PAGE_SIZE).toBe(6);
        expect(result.current.page).toBe(1);
        expect(result.current.pageCount).toBe(3);
        expect(result.current.pageItems).toEqual(items.slice(0, 6));
        expect(result.current.rangeStart).toBe(1);
        expect(result.current.rangeEnd).toBe(6);

        act(() => result.current.setPage(3));

        expect(result.current.pageItems).toEqual(items.slice(12, 15));
        expect(result.current.rangeStart).toBe(13);
        expect(result.current.rangeEnd).toBe(15);
    });

    it('recorta la página cuando los filtros reducen el total', () => {
        const { result, rerender } = renderHook(
            ({ coleccion }) => useClientPagination(coleccion),
            { initialProps: { coleccion: items } }
        );

        act(() => result.current.setPage(3));
        expect(result.current.page).toBe(3);

        rerender({ coleccion: items.slice(0, 4) });

        expect(result.current.page).toBe(1);
        expect(result.current.pageCount).toBe(1);
        expect(result.current.pageItems).toHaveLength(4);
    });

    it('normaliza páginas fuera de rango y tamaños no ofrecidos', () => {
        const { result } = renderHook(() => useClientPagination(items));

        act(() => result.current.setPage(0));
        expect(result.current.page).toBe(1);

        act(() => result.current.setPage(99));
        expect(result.current.page).toBe(3);

        act(() => result.current.setPage(Number.NaN));
        expect(result.current.page).toBe(1);

        act(() => result.current.setPage(2));
        act(() => result.current.setPageSize(5));
        expect(result.current.pageSize).toBe(DEFAULT_PAGE_SIZE);
        expect(result.current.page).toBe(1);

        act(() => result.current.setPageSize(12));
        expect(result.current.pageSize).toBe(12);
        expect(result.current.pageCount).toBe(2);
    });

    it('reinicia la página al cambiar dependencias, pero no en el montaje', () => {
        const { result, rerender } = renderHook(
            ({ filtro }) => useClientPagination(items, { resetDeps: [filtro] }),
            { initialProps: { filtro: '' } }
        );

        expect(result.current.page).toBe(1);
        act(() => result.current.setPage(2));
        expect(result.current.page).toBe(2);

        rerender({ filtro: '' });
        expect(result.current.page).toBe(2);

        rerender({ filtro: 'nuevo' });
        expect(result.current.page).toBe(1);
    });

    it('devuelve un rango 0–0 para colecciones vacías', () => {
        const { result } = renderHook(() => useClientPagination([]));

        expect(result.current.pageCount).toBe(1);
        expect(result.current.pageItems).toEqual([]);
        expect(result.current.rangeStart).toBe(0);
        expect(result.current.rangeEnd).toBe(0);
    });

    it('resetPage vuelve a la primera página sin cambiar el tamaño', () => {
        const { result } = renderHook(() => useClientPagination(items, { defaultPageSize: 12 }));

        act(() => result.current.setPage(2));
        act(() => result.current.resetPage());

        expect(result.current.page).toBe(1);
        expect(result.current.pageSize).toBe(12);
    });
});
