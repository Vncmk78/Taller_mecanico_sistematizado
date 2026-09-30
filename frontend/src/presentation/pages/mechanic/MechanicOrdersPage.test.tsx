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

// Fallo de transporte: error Axios sin respuesta HTTP, así que isOfflineError
// lo clasifica como "sin conexión" (no como error del servidor).
const axiosNetworkError = { isAxiosError: true };
// Error del servidor: llegó respuesta con status 500, así que no es "sin conexión".
const axiosServerError = { isAxiosError: true, response: { status: 500, data: {} } };

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

  it('offline conserva la caché con las órdenes asignadas al mecánico', async () => {
    useOrderStore.setState({ orders: [ordA, ordB, ordC], isOffline: true });
    vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

    renderPage();

    expect(
      await screen.findByText(/No se pudo conectar con el servidor/)
    ).toBeInTheDocument();
    // La caché ya viene filtrada por la Gateway, así que offline se conserva
    // tal cual y el mecánico se identifica con su id real.
    expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
    expect(screen.getByText('Mecánico: m1')).toBeInTheDocument();
    expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
    expect(screen.getByText('Orden n° 103')).toBeInTheDocument();
  });

    it('muestra el estado vacío cuando no tiene órdenes asignadas', async () => {
        // La Gateway devuelve solo las órdenes del mecánico: una caché vacía
        // significa que no tiene ninguna asignada.
        useOrderStore.setState({ orders: [], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

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

    it('un error del servidor sin caché muestra el estado de error, no el banner offline', async () => {
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosServerError);

        renderPage();

        expect(await screen.findByText('No se pudieron cargar sus órdenes')).toBeInTheDocument();
        expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
    });

    it('con error del servidor y caché previa avisa pero conserva las órdenes', async () => {
        useOrderStore.setState({
            orders: [ordA],
            status: 'error',
            error: 'El servidor tuvo un problema. Intente más tarde.',
            isOffline: false,
        });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosServerError);

        renderPage();

        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByRole('alert')).toHaveTextContent('El servidor tuvo un problema.');
    });
});