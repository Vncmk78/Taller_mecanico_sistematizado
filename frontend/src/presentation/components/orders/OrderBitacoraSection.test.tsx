import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { BitacoraEntry } from '@/domain/entities/Bitacora';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderBitacoraStore } from '@/infrastructure/stores/useOrderBitacoraStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { OrderBitacoraSection } from './OrderBitacoraSection';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrderBitacora: vi.fn(),
        registrarBitacora: vi.fn(),
    },
}));

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

const entrada: BitacoraEntry = {
    id: '77',
    ordenId: '101',
    autorUsuarioId: '50',
    tipo: 'accion',
    descripcion: 'Se reemplazaron las pastillas delanteras',
    creadoEn: '2026-09-28T12:15:00-03:00',
    repuestos: [{ nombre: 'Pastillas de freno', cantidad: 2 }],
};

function renderSection(canWrite: boolean) {
    return render(
        <ToastProvider>
            <OrderBitacoraSection order={orden} canWrite={canWrite} />
        </ToastProvider>
    );
}

beforeEach(() => {
    useOrderBitacoraStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
    useOrderStore.setState({ isOffline: false });
    vi.clearAllMocks();
});

describe('OrderBitacoraSection', () => {
    it('lista las entradas cargadas del servidor', async () => {
        vi.mocked(orderService.getOrderBitacora).mockResolvedValue([entrada]);

        renderSection(false);

        expect(await screen.findByText('Bitácora de trabajo')).toBeInTheDocument();
        expect(await screen.findByText('Se reemplazaron las pastillas delanteras')).toBeInTheDocument();
        expect(orderService.getOrderBitacora).toHaveBeenCalledWith('101');
    });

    it('no muestra el formulario cuando el rol no puede escribir', async () => {
        vi.mocked(orderService.getOrderBitacora).mockResolvedValue([]);

        renderSection(false);

        expect(await screen.findByText('Bitácora de trabajo')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Registrar entrada' })).not.toBeInTheDocument();
    });

    it('muestra el formulario cuando el rol puede escribir', async () => {
        vi.mocked(orderService.getOrderBitacora).mockResolvedValue([]);

        renderSection(true);

        expect(await screen.findByRole('button', { name: 'Registrar entrada' })).toBeInTheDocument();
    });
});
