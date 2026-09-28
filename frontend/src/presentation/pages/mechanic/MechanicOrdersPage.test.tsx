import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { MechanicOrdersPage } from './MechanicOrdersPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

function orden(id: string, estadoCodigo: number, mecanicoActualId: string | null): Order {
    return {
        id,
        vehicleId: '1',
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: `PT-${id}`,
        vehiculo: `Vehículo ${id}`,
    };
}

const ordA = orden('101', 5, 'm1');
const ordB = orden('102', 3, 'm2');
const ordC = orden('103', 1, null);

function renderPage() {
    return render(
        <MemoryRouter>
            <MechanicOrdersPage />
        </MemoryRouter>
    );
}

describe('MechanicOrdersPage: mis órdenes del mecánico', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('online muestra todas las órdenes asignadas', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordA, ordB, ordC]);

        renderPage();

        expect(await screen.findByText('Mis Órdenes')).toBeInTheDocument();
        expect(
            screen.getByText('Órdenes de trabajo asignadas a tu cuenta')
        ).toBeInTheDocument();
        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 103')).toBeInTheDocument();
    });

    it('offline filtra por el mecánico actual y mantiene la caché', async () => {
        useOrderStore.setState({ orders: [ordA, ordB, ordC], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(new Error('network'));

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Mecánico: Martín Herrera')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 102')).not.toBeInTheDocument();
        expect(screen.queryByText('Orden n° 103')).not.toBeInTheDocument();
    });

    it('muestra el estado vacío cuando no tiene órdenes asignadas', async () => {
        useOrderStore.setState({ orders: [ordB], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(new Error('network'));

        renderPage();

        expect(
            await screen.findByText('No tiene órdenes asignadas por el momento.')
        ).toBeInTheDocument();
    });

    it('muestra el skeleton mientras carga', () => {
        vi.mocked(orderService.getOrders).mockImplementation(() => new Promise<Order[]>(() => {}));

        const { container } = renderPage();

        expect(container.querySelector('.animate-pulse')).not.toBeNull();
    });
});