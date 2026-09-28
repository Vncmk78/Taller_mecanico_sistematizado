import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { AdminOrdersPage } from './AdminOrdersPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

function orden(id: string, estadoCodigo: number, patente: string, actualizadoEn: string): Order {
    return {
        id,
        vehicleId: '1',
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn,
        patente,
        vehiculo: `Vehículo ${id}`,
    };
}

const ord1 = orden('1', 5, 'ABCD-12', '2026-09-05T16:30:00');
const ord2 = orden('2', 1, 'EFGH-34', '2026-09-04T12:00:00');
const ord3 = orden('3', 5, 'IJKL-56', '2026-09-03T10:00:00');

const ocho = Array.from({ length: 8 }, (_, i) =>
    orden(
        String(i + 1),
        i % 2 === 0 ? 5 : 1,
        `PT-${i}`,
        `2026-09-${String(i + 1).padStart(2, '0')}T12:00:00`
    )
);

// Error de red simulado: es un error Axios pero sin respuesta HTTP del servidor.
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter>
            <AdminOrdersPage />
        </MemoryRouter>
    );
}

describe('AdminOrdersPage: listado de órdenes (filtros, paginación, offline)', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('carga y muestra las órdenes con su estado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ord1, ord2]);

        renderPage();

        expect(await screen.findByText('Gestión de Órdenes')).toBeInTheDocument();
        expect(await screen.findByText('Orden n° 1')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 2')).toBeInTheDocument();
        expect(screen.getByText('ABCD-12')).toBeInTheDocument();
        expect(screen.getByTitle('En reparación')).toBeInTheDocument();
        expect(screen.getByTitle('Recibido')).toBeInTheDocument();
    });

    it('filtra por búsqueda y muestra el mensaje vacío', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ord1, ord2, ord3]);

        renderPage();
        await screen.findByText('Orden n° 3');

        fireEvent.change(screen.getByLabelText('Buscar órdenes'), { target: { value: 'EFGH' } });

        expect(screen.queryByText('Orden n° 1')).not.toBeInTheDocument();
        expect(screen.getByText('Orden n° 2')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Buscar órdenes'), { target: { value: 'zzz' } });

        expect(
            await screen.findByText('No se encontraron órdenes para "zzz".')
        ).toBeInTheDocument();
    });

    it('filtra por estado y muestra el mensaje vacío por estado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ord1, ord2, ord3]);

        renderPage();
        await screen.findByText('Orden n° 3');

        fireEvent.change(screen.getByLabelText('Filtrar por estado'), { target: { value: '1' } });

        expect(screen.queryByText('Orden n° 1')).not.toBeInTheDocument();
        expect(screen.getByText('Orden n° 2')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Filtrar por estado'), { target: { value: '6' } });

        expect(
            await screen.findByText('No hay órdenes en el estado "Listo".')
        ).toBeInTheDocument();
    });

    it('pagina cuando el total supera el tamaño de página', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue(ocho);

        renderPage();
        // Más reciente primero: la primera página muestra las ids 8..3.
        await screen.findByText('Orden n° 8');
        expect(screen.getByText('Mostrando 1–6 de 8 órdenes')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 1')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));

        expect(await screen.findByText('Orden n° 1')).toBeInTheDocument();
    });

    it('muestra el skeleton mientras carga', () => {
        vi.mocked(orderService.getOrders).mockImplementation(() => new Promise<Order[]>(() => {}));

        const { container } = renderPage();

        expect(container.querySelector('.animate-pulse')).not.toBeNull();
    });

    it('queda offline con banner y conserva la caché', async () => {
        useOrderStore.setState({ orders: [ord1], isOffline: false });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        expect(screen.getByText('Orden n° 1')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    });
});