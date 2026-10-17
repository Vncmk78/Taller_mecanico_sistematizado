import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ClientOrdersPage } from './ClientOrdersPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

function orden(id: string, vehicleId: string, estadoCodigo: number): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: `PT-${id}`,
        vehiculo: `Vehículo ${id}`,
    };
}

// Las órdenes se asocian a un cliente a través de sus vehículos; aquí se
// cubren los vehículos 1, 2 y 6 para comprobar que la vista no inventa datos.
const ordVeh1 = orden('101', '1', 5);
const ordVeh2 = orden('102', '2', 3);
const ordVeh6 = orden('106', '6', 6);

// Fallo de transporte: error Axios sin respuesta HTTP, así que isOfflineError
// lo clasifica como "sin conexión" (no como error del servidor).
const axiosNetworkError = { isAxiosError: true };
// Error del servidor: llegó respuesta con status 500, así que no es "sin conexión".
const axiosServerError = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientOrdersPage />
        </MemoryRouter>
    );
}

describe('ClientOrdersPage: mis órdenes del cliente', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('online muestra todas las órdenes', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordVeh1, ordVeh2, ordVeh6]);

        renderPage();

        expect(await screen.findByText('Mis Órdenes')).toBeInTheDocument();
        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 106')).toBeInTheDocument();
    });

  it('offline conserva la caché con las órdenes del cliente', async () => {
    useOrderStore.setState({ orders: [ordVeh1, ordVeh2, ordVeh6], isOffline: true });
    vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

    renderPage();

    expect(
      await screen.findByText(/No se pudo conectar con el servidor/)
    ).toBeInTheDocument();
    // La caché ya viene filtrada por la Gateway, así que offline se conserva
    // tal cual sin volver a filtrar por un cliente de ejemplo.
    expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
    expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
    expect(screen.getByText('Orden n° 106')).toBeInTheDocument();
  });

  it('muestra el estado vacío cuando el cliente no tiene órdenes', async () => {
    useOrderStore.setState({ orders: [], isOffline: true });
    vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

    renderPage();

    expect(
      await screen.findByText('Aún no tiene órdenes de trabajo registradas.')
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
});