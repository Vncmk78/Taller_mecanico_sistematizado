import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Order } from '@/domain/entities/Order';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';
import { OrderStatusAndHistory } from './OrderStatusAndHistory';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: { getOrderHistory: vi.fn() },
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

const historialOrden101: OrderHistoryEntry[] = [
    {
        id: 'h-101-1',
        ordenId: '101',
        estadoAnteriorCodigo: null,
        estadoNuevoCodigo: 1,
        actorUsuarioId: null,
        origen: 'sistema',
        fecha: '2026-09-01T10:15:00',
        observacion: 'Ingreso registrado por el administrador',
    },
    {
        id: 'h-101-2',
        ordenId: '101',
        estadoAnteriorCodigo: 1,
        estadoNuevoCodigo: 2,
        actorUsuarioId: 7,
        origen: 'usuario',
        fecha: '2026-09-01T11:00:00',
        observacion: 'Asignada a Martín Herrera',
        usuarioNombre: 'Administrador del taller',
    },
    {
        id: 'h-101-3',
        ordenId: '101',
        estadoAnteriorCodigo: 2,
        estadoNuevoCodigo: 3,
        actorUsuarioId: 1,
        origen: 'usuario',
        fecha: '2026-09-02T09:20:00',
        observacion: 'Presupuesto v1 enviado al cliente',
        usuarioNombre: 'Martín Herrera',
    },
];

describe('OrderStatusAndHistory: contrato de reuso (estado + historial)', () => {
    beforeEach(() => {
        useOrderHistoryStore.setState({ entries: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('con un solo contrato (prop order) expone estado e historial, para incrustarlo en cualquier portal', async () => {
        vi.mocked(orderService.getOrderHistory).mockResolvedValue(historialOrden101);

        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByText('Presupuesto v1 enviado al cliente')).toBeInTheDocument();
        expect(
            screen.getByRole('heading', { name: 'Ciclo de estados de la orden' })
        ).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Historial de estados' })).toBeInTheDocument();
        expect(screen.getByRole('list', { name: 'Ciclo de estados de la orden' })).toBeInTheDocument();
        expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('En reparación');
    });

    it('sin conexión conserva el historial en caché y avisa, sin mostrar el estado vacío', async () => {
        useOrderHistoryStore.setState({
            entries: historialOrden101,
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.mocked(orderService.getOrderHistory).mockRejectedValue({ isAxiosError: true });

        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByText('Presupuesto v1 enviado al cliente')).toBeInTheDocument();
        expect(screen.getByText(/Mostrando datos disponibles localmente/)).toBeInTheDocument();
        expect(screen.getByText('Reintentar')).toBeInTheDocument();
        expect(
            screen.queryByText('Aún no hay registros del historial de estados de esta orden.')
        ).not.toBeInTheDocument();
    });

    it('un error del servidor en el historial conserva la caché y deja el seguimiento visible', async () => {
        useOrderHistoryStore.setState({
            entries: historialOrden101,
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.mocked(orderService.getOrderHistory).mockRejectedValue({
            isAxiosError: true,
            response: { status: 500, data: {} },
        });

        render(<OrderStatusAndHistory order={orden} />);

        expect(await screen.findByText('Presupuesto v1 enviado al cliente')).toBeInTheDocument();
        expect(screen.getByText(/Mostrando datos disponibles localmente/)).toBeInTheDocument();
        expect(
            screen.queryByText('Aún no hay registros del historial de estados de esta orden.')
        ).not.toBeInTheDocument();
    });
});