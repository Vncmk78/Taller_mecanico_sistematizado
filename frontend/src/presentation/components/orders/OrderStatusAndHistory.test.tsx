import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Order } from '@/domain/entities/Order';
import { mockOrderHistory } from '@/infrastructure/mocks/orders.history.mock';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { OrderStatusAndHistory } from './OrderStatusAndHistory';

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
        useOrderHistoryStore.setState({ entries: [] });
        render(<OrderStatusAndHistory order={orden} />);

        expect(
            await screen.findByText('Aún no hay registros del historial de estados de esta orden.')
        ).toBeInTheDocument();
    });
});