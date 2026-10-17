import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { mockAssignedVehicleIds, mockVehicles } from '@/infrastructure/mocks/vehicles.mock';
import { orderService } from '@/infrastructure/api/OrderService';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { MechanicVehiclesPage } from '@/presentation/pages/mechanic/MechanicVehiclesPage';

const vehiculosAsignados = mockVehicles.filter((v) => mockAssignedVehicleIds.includes(v.id));

// Identidad real de la sesión (usuario_id de MS1), la misma que la Gateway usa
// para filtrar las órdenes del mecánico.
const MECANICO_ID = 'm1';

function orden(id: string, vehicleId: string, mecanicoActualId: string): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo: 5,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
    };
}

// Las órdenes del mecánico: sus vehículos son el 1 y el 2.
const ordenesDelMecanico = [orden('101', '1', MECANICO_ID), orden('102', '2', MECANICO_ID)];
// Una orden de otro mecánico que también apunta al vehículo 1.
const ordenDeOtro = orden('103', '1', 'm2');

vi.mock('@/infrastructure/stores/useVehicleStore', () => ({
    useVehicleStore: vi.fn(),
}));

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
    },
}));

function renderPage() {
    return render(
        <MemoryRouter>
            <MechanicVehiclesPage />
        </MemoryRouter>
    );
}

describe('MechanicVehiclesPage: buscador de vehículos asignados', () => {
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
        useOrderStore.setState({ orders: ordenesDelMecanico, status: 'success', error: null });
        vi.clearAllMocks();
        // La página carga las órdenes del mecánico para acotar la caché de vehículos.
        vi.mocked(orderService.getOrders).mockResolvedValue(ordenesDelMecanico);
    });

    it('expone el campo de búsqueda con un nombre accesible', () => {
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: vehiculosAsignados,
            status: 'success',
            error: null,
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(
            screen.getByRole('textbox', { name: 'Buscar por patente, marca o modelo' })
        ).toBeInTheDocument();
    });

    it('filtra los vehículos asignados al escribir en la búsqueda', () => {
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: vehiculosAsignados,
            status: 'success',
            error: null,
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();

        fireEvent.change(screen.getByRole('textbox', { name: 'Buscar por patente, marca o modelo' }), {
            target: { value: 'ABCD-12' },
        });

        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.queryByText('Nissan Kicks')).not.toBeInTheDocument();
    });

    it('descarta los vehículos que no están en las órdenes del mecánico, aunque la caché los tenga', () => {
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: mockVehicles,
            status: 'success',
            error: null,
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('Nissan Kicks')).toBeInTheDocument();
        // El vehículo 3 no aparece en ninguna orden del mecánico.
        expect(screen.queryByText('Hyundai Tucson')).not.toBeInTheDocument();
    });

    it('offline acota la caché compartida a los vehículos de sus órdenes', () => {
        // Sesión anterior de otro portal: la caché en memoria traía todos los
        // vehículos, pero el mecánico solo debe ver los suyos.
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: mockVehicles,
            status: 'success',
            error: null,
            isOffline: true,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('Nissan Kicks')).toBeInTheDocument();
        expect(screen.queryByText('Hyundai Tucson')).not.toBeInTheDocument();
    });

    it('mantiene un vehículo si alguna orden del mecánico lo referencia, aunque sea de otro mecánico', () => {
        useOrderStore.setState({ orders: [...ordenesDelMecanico, ordenDeOtro], status: 'success' });
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: vehiculosAsignados,
            status: 'success',
            error: null,
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('Nissan Kicks')).toBeInTheDocument();
    });

    it('muestra el estado vacío cuando no hay vehículos asignados', () => {
        useOrderStore.setState({ orders: [], status: 'success' });
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: [],
            status: 'success',
            error: null,
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('No tiene vehículos asignados por el momento.')).toBeInTheDocument();
    });

    it('un error del servidor sin caché muestra el estado de error, no el banner offline', () => {
        useOrderStore.setState({ orders: [], status: 'success' });
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: [],
            status: 'error',
            error: 'El servidor tuvo un problema. Intente más tarde.',
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('No se pudieron cargar los vehículos')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
        expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
    });

    it('con error del servidor y caché previa avisa pero conserva los vehículos', () => {
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: vehiculosAsignados,
            status: 'error',
            error: 'El servidor tuvo un problema. Intente más tarde.',
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByRole('alert')).toHaveTextContent('El servidor tuvo un problema.');
    });

    it('muestra el identificador real del propietario en lugar de un nombre simulado', () => {
        vi.mocked(useVehicleStore).mockReturnValue({
            vehicles: vehiculosAsignados,
            status: 'success',
            error: null,
            isOffline: false,
            requestId: null,
            fetchVehicles: vi.fn(),
        });

        renderPage();

        expect(
            screen.getByText(`Dueño: Cliente #${vehiculosAsignados[0].clientId}`)
        ).toBeInTheDocument();
    });
});