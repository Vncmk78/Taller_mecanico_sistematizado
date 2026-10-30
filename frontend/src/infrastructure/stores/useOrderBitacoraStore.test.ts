import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BitacoraEntry } from '@/domain/entities/Bitacora';
import { sinRespuesta } from '@/infrastructure/mocks/payloads.reales';
import { useOrderBitacoraStore } from './useOrderBitacoraStore';

function entrada(overrides: Partial<BitacoraEntry> = {}): BitacoraEntry {
    return {
        id: '1',
        ordenId: '31',
        autorUsuarioId: '50',
        tipo: 'accion',
        descripcion: 'Acción',
        creadoEn: '2026-09-28T12:15:00-03:00',
        repuestos: [],
        ...overrides,
    };
}

beforeEach(() => {
    useOrderBitacoraStore.setState({
        entries: [],
        status: 'idle',
        error: null,
        isOffline: false,
        requestId: null,
    });
    vi.clearAllMocks();
});

describe('useOrderBitacoraStore', () => {
    it('carga la bitácora de una orden y reemplaza solo sus entradas', async () => {
        useOrderBitacoraStore.setState({ entries: [entrada({ id: '9', ordenId: 'otra' })] });

        await useOrderBitacoraStore.getState().fetchOrderBitacora('31', async () => [
            entrada({ id: '1' }),
            entrada({ id: '2' }),
        ]);

        const { entries, status } = useOrderBitacoraStore.getState();
        expect(status).toBe('success');
        expect(entries.map((e) => e.id).sort()).toEqual(['1', '2', '9']);
    });

    it('ante un fallo de transporte conserva la caché y marca isOffline', async () => {
        useOrderBitacoraStore.setState({ entries: [entrada({ id: '1' })] });

        await useOrderBitacoraStore
            .getState()
            .fetchOrderBitacora('31', async () => {
                throw sinRespuesta;
            });

        const state = useOrderBitacoraStore.getState();
        expect(state.status).toBe('error');
        expect(state.isOffline).toBe(true);
        expect(state.entries.map((e) => e.id)).toEqual(['1']);
    });

    it('addEntry inserta una entrada nueva y actualiza una existente por id', () => {
        const { addEntry } = useOrderBitacoraStore.getState();

        addEntry(entrada({ id: '1', descripcion: 'Primera' }));
        addEntry(entrada({ id: '2', descripcion: 'Segunda' }));
        addEntry(entrada({ id: '1', descripcion: 'Primera editada' }));

        const { entries } = useOrderBitacoraStore.getState();
        expect(entries).toHaveLength(2);
        expect(entries.find((e) => e.id === '1')?.descripcion).toBe('Primera editada');
    });

    it('reset vacía las entradas y el estado asíncrono', () => {
        useOrderBitacoraStore.setState({ entries: [entrada()], status: 'success' });

        useOrderBitacoraStore.getState().reset();

        expect(useOrderBitacoraStore.getState().entries).toEqual([]);
        expect(useOrderBitacoraStore.getState().status).toBe('idle');
    });
});
