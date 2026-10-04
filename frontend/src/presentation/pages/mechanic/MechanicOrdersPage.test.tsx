import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { MechanicOrdersPage } from './MechanicOrdersPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAssignedVehicles: vi.fn(),
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

// Identidad real de la sesión (usuario_id de MS1).
const MECANICO_ID = 'm1';
const ordA = orden('101', 5, MECANICO_ID);
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
        useAuthStore.setState({
            user: {
                id: MECANICO_ID,
                email: 'mecanico@taller.cl',
                full_name: 'Mecánico Prueba',
                role: 'mecanico',
                is_active: true,
            },
        });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
        // Sin vehículos asignados la lista cae al identificador interno del vehicleId.
        vi.mocked(vehicleService.getAssignedVehicles).mockResolvedValue([]);
    });

    it('online muestra las órdenes asignadas al mecánico autenticado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordA]);

        renderPage();

        expect(await screen.findByText('Mis Órdenes')).toBeInTheDocument();
        expect(
            screen.getByText('Órdenes de trabajo asignadas a tu cuenta')
        ).toBeInTheDocument();
        expect(await screen.findByText('Orden n° 101')).toBeInTheDocument();
    });

    it('carga los vehículos asignados para poder mostrar patente y modelo', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordA]);
        vi.mocked(vehicleService.getAssignedVehicles).mockResolvedValue([
            { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 85120, clientId: 'c1' },
        ]);

        renderPage();

        await screen.findByText('Orden n° 101');

        expect(vehicleService.getAssignedVehicles).toHaveBeenCalled();
    });

    it('descarta las órdenes de otros mecánicos aunque estén en la caché', async () => {
        useOrderStore.setState({ orders: [ordA, ordB, ordC], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(
            await screen.findByText(/No se pudo conectar con el servidor/)
        ).toBeInTheDocument();
        // Segunda barrera de alcance: la caché compartida puede traer órdenes de
        // otra sesión, así que se comparan contra el usuario_id de MS1.
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('Mecánico: m1')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 102')).not.toBeInTheDocument();
        expect(screen.queryByText('Orden n° 103')).not.toBeInTheDocument();
    });

    it('busca también por el nombre del estado', async () => {
        useOrderStore.setState({ orders: [orden('101', 5, MECANICO_ID), orden('102', 1, MECANICO_ID)] });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        await screen.findByText('Orden n° 101');
        await screen.findByText('Orden n° 102');

        fireEvent.change(
            screen.getByPlaceholderText('Buscar por n° de orden, patente o estado...'),
            { target: { value: 'Recibido' } }
        );

        expect(screen.queryByText('Orden n° 101')).not.toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
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