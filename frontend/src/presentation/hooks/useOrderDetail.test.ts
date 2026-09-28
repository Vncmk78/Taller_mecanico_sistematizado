import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { Order } from '@/domain/entities/Order';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useOrderDetail } from './useOrderDetail';

const orden: Order = {
    id: '101',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 5,
    mecanicoActualId: 'm1',
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:15:00',
    actualizadoEn: '2026-09-05T16:30:00',
};

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };

describe('useOrderDetail: carga del detalle de una orden', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('carga la orden y la expone sin marcar notFound', async () => {
        const loader = vi.fn((_id: string) => Promise.resolve(orden));

        const { result } = renderHook(() => useOrderDetail('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.order?.id).toBe('101');
        expect(result.current.notFound).toBe(false);
    });

    it('marca notFound cuando el backend responde 404', async () => {
        const loader = vi.fn((_id: string) => Promise.reject(axios404));

        const { result } = renderHook(() => useOrderDetail('999', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.notFound).toBe(true);
        expect(result.current.order).toBeUndefined();
    });

    it('conserva la caché local ante un error de red sin marcar notFound', async () => {
        useOrderStore.setState({ orders: [orden] });
        const loader = vi.fn((_id: string) => Promise.reject(new Error('network')));

        const { result } = renderHook(() => useOrderDetail('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.order?.id).toBe('101');
        expect(result.current.notFound).toBe(false);
        expect(useOrderStore.getState().isOffline).toBe(true);
    });

    it('con id indefinido marca notFound sin invocar el loader', async () => {
        const loader = vi.fn((_id: string) => Promise.resolve(orden));

        const { result } = renderHook(() => useOrderDetail(undefined, loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.notFound).toBe(true);
        expect(loader.mock.calls).toHaveLength(0);
    });

    it('refetch vuelve a invocar el loader', async () => {
        const loader = vi.fn((_id: string) => Promise.resolve(orden));

        const { result } = renderHook(() => useOrderDetail('101', loader));

        await waitFor(() => expect(result.current.loading).toBe(false));
        act(() => result.current.refetch());

        expect(loader.mock.calls).toHaveLength(2);
    });
});