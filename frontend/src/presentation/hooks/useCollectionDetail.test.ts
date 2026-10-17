import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useCollectionDetail } from './useCollectionDetail';

interface TestItem {
    id: string;
    name: string;
}

const item1: TestItem = { id: '1', name: 'a' };

describe('useCollectionDetail: carga de detalle de un item', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('expone el item de la caché y desactiva loading al resolver', async () => {
        const fetchById = vi.fn(() => Promise.resolve({ notFound: false, failed: false }));

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: '1', items: [item1], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.item?.id).toBe('1');
        expect(result.current.notFound).toBe(false);
        expect(fetchById).toHaveBeenCalledWith('1', expect.any(Function));
    });

    it('marca notFound cuando el backend responde 404', async () => {
        const fetchById = vi.fn(() => Promise.resolve({ notFound: true, failed: false }));

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: '999', items: [], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.notFound).toBe(true);
        expect(result.current.item).toBeUndefined();
    });

    it('con id indefinido marca notFound sin invocar fetchById', async () => {
        const fetchById = vi.fn(() => Promise.resolve({ notFound: false, failed: false }));

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: undefined, items: [], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.notFound).toBe(true);
        expect(fetchById).not.toHaveBeenCalled();
    });

    it('marca failed cuando el fetch falla sin copia local', async () => {
        const fetchById = vi.fn(() => Promise.resolve({ notFound: false, failed: true }));

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: '999', items: [], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.failed).toBe(true);
        expect(result.current.notFound).toBe(false);
    });

    it('un fallo con copia local no marca failed ni notFound', async () => {
        const fetchById = vi.fn(() => Promise.resolve({ notFound: false, failed: false }));

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: '1', items: [item1], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.failed).toBe(false);
        expect(result.current.notFound).toBe(false);
        expect(result.current.item?.id).toBe('1');
    });

    it('refetch vuelve a invocar fetchById', async () => {
        const fetchById = vi.fn(() => Promise.resolve({ notFound: false, failed: false }));

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: '1', items: [item1], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(false));
        act(() => result.current.refetch());

        expect(fetchById.mock.calls).toHaveLength(2);
    });

    it('alterna loading mientras la petición está pendiente', async () => {
        let resolveFetch: (value: { notFound: boolean; failed: boolean }) => void = () => {};
        const fetchById = vi.fn(
            () => new Promise<{ notFound: boolean; failed: boolean }>((resolve) => {
                resolveFetch = resolve;
            })
        );

        const { result } = renderHook(() =>
            useCollectionDetail<TestItem>({ id: '1', items: [item1], fetchById, loader: vi.fn() })
        );

        await waitFor(() => expect(result.current.loading).toBe(true));
        act(() => resolveFetch({ notFound: false, failed: false }));
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.item?.id).toBe('1');
    });
});