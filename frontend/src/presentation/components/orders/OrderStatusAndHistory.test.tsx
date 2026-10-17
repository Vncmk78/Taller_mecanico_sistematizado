import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { mockOrderHistory } from '@/infrastructure/mocks/orders.history.mock';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { OrderStatusAndHistory } from './OrderStatusAndHistory';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrderHistory: vi.fn(),
    },
}));

// Error del servidor: llegó respuesta con status 500, así que no es "sin conexión".
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };
const errorServidor = 'El servidor tuvo un problema. Intente más tarde.';

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

describe('OrderStatusAndHistory: representación visual de estados e historial', () => {
    beforeEach(() => {
        useOrderHistoryStore.setState({
            entries: mockOrderHistory,
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.clearAllMocks();
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(mockOrderHistory);
    });

    it('renderiza el ciclo completo de 8 estados y resalta la etapa actual', () => {
        render(<OrderStatusAndHistory order={orden} />);

        expect(screen.getByRole('heading', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')).toHaveLength(8);
        const current = screen.getByRole('listitem', { current: 'step' });
        expect(current).toHaveTextContent('En reparación');
    });

    it('muestra el historial de estados de la orden con responsable y observación', async () => {
        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByText('Ingreso registrado por el administrador')).toBeInTheDocument();
        expect(screen.getAllByText('desde Recibido')).toHaveLength(1);
        expect(screen.getByText('Martín Herrera')).toBeInTheDocument();
        expect(screen.getAllByText('Sistema').length).toBeGreaterThan(0);
    });

    it('muestra estado vacío cuando la orden no tiene historial', async () => {
        vi.mocked(orderService.getOrderHistory).mockResolvedValue([]);
        render(<OrderStatusAndHistory order={orden} />);

        expect(
            await screen.findByText('Aún no hay registros del historial de estados de esta orden.')
        ).toBeInTheDocument();
    });

    it('con error del servidor avisa sin presentarlo como "sin conexión"', async () => {
        useOrderHistoryStore.setState({ entries: [] });
        vi.mocked(orderService.getOrderHistory).mockRejectedValue(axios500);

        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByRole('alert')).toHaveTextContent('El servidor tuvo un problema.');
        expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
        // Un fallo de fetch no es un historial vacío.
        expect(
            screen.queryByText('Aún no hay registros del historial de estados de esta orden.')
        ).not.toBeInTheDocument();
        expect(
            await screen.findByText('No fue posible mostrar el historial de estados de esta orden.')
        ).toBeInTheDocument();
    });

    it('con error del servidor y caché previa conserva las entradas del historial', async () => {
        useOrderHistoryStore.setState({
            entries: mockOrderHistory,
            status: 'error',
            error: errorServidor,
            isOffline: false,
        });
        vi.mocked(orderService.getOrderHistory).mockRejectedValue(axios500);

        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByText('Ingreso registrado por el administrador')).toBeInTheDocument();
        expect(screen.getByRole('alert')).toHaveTextContent('El servidor tuvo un problema.');
    });

    it('mantiene el ciclo de estados visible aunque falle el historial', async () => {
        vi.mocked(orderService.getOrderHistory).mockRejectedValue(axios500);

        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByRole('heading', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
    });

    it('un fallo de transporte sí usa el banner de sin conexión', async () => {
        vi.mocked(orderService.getOrderHistory).mockRejectedValue({ isAxiosError: true });

        render(<OrderStatusAndHistory order={orden} />);

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
    });
});