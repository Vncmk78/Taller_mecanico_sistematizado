import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { useOrderHistory } from './useOrderHistory';

const e1: OrderHistoryEntry = {
    id: 'h1',
    ordenId: '101',
    estadoAnteriorCodigo: 3,
    estadoNuevoCodigo: 5,
    actorUsuarioId: 1,
    origen: 'usuario',
    fecha: '2026-09-02T12:00:00',
    observacion: 'a',
    usuarioNombre: 'Martín Herrera',
};

const e2: OrderHistoryEntry = {
    id: 'h2',
    ordenId: '101',
    estadoAnteriorCodigo: null,
    estadoNuevoCodigo: 1,
    actorUsuarioId: null,
    origen: 'sistema',
    fecha: '2026-09-01T10:15:00',
    observacion: 'b',
};

const e3: OrderHistoryEntry = {
    id: 'h3',
    ordenId: '999',
    estadoAnteriorCodigo: null,
    estadoNuevoCodigo: 1,
    actorUsuarioId: null,
    origen: 'sistema',
    fecha: '2026-09-03T00:00:00',
    observacion: 'c',
};

describe('useOrderHistory: historial de estados de una orden', () => {
    beforeEach(() => {
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('filtra por orden y ordena de más reciente a más antigua', async () => {
        // El fetch falla (offline) y se conserva la caché para ver el ordenado.
        useOrderHistoryStore.setState({ entries: [e2, e3, e1] });
        const loader = vi.fn((_ordenId: string) => Promise.reject(new Error('network')));

        const { result } = renderHook(() => useOrderHistory('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.entries.map((e) => e.id)).toEqual(['h1', 'h2']);
    });

    it('reemplaza el historial de la orden cuando el fetch responde', async () => {
        const loader = vi.fn((_ordenId: string) => Promise.resolve([e1, e2]));

        const { result } = renderHook(() => useOrderHistory('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.entries.map((e) => e.id)).toEqual(['h1', 'h2']);
        expect(useOrderHistoryStore.getState().isOffline).toBe(false);
    });

    it('alterna el flag de loading durante el fetch', async () => {
        let resolveFetch: (value: OrderHistoryEntry[]) => void = () => {};
        const loader = vi.fn(
            (_ordenId: string) => new Promise<OrderHistoryEntry[]>((resolve) => {
                resolveFetch = resolve;
            })
        );

        const { result } = renderHook(() => useOrderHistory('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(true));
        act(() => resolveFetch([]));
        await waitFor(() => expect(result.current.loading).toBe(false));
    });

    it('con id indefinido no invoca el loader y devuelve lista vacía', async () => {
        const loader = vi.fn((_ordenId: string) => Promise.resolve([]));

        const { result } = renderHook(() => useOrderHistory(undefined, loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.entries).toEqual([]);
        expect(loader.mock.calls).toHaveLength(0);
    });

    it('refetch vuelve a invocar el loader', async () => {
        const loader = vi.fn((_ordenId: string) => Promise.resolve([e1, e2]));

        const { result } = renderHook(() => useOrderHistory('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        act(() => result.current.refetch());

        expect(loader.mock.calls).toHaveLength(2);
    });
});