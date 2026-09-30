import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { mockVehicles } from '@/infrastructure/mocks/vehicles.mock';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { AdminVehiclesPage } from './AdminVehiclesPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAllVehicles: vi.fn(),
        getMyVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
    },
}));

// Fallo de transporte: error Axios sin respuesta HTTP (isOfflineError → true).
const axiosNetworkError = { isAxiosError: true };
// Error del servidor: llegó respuesta con status 500 (isOfflineError → false).
const axiosServerError = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter>
            <AdminVehiclesPage />
        </MemoryRouter>
    );
}

describe('AdminVehiclesPage: catálogo de vehículos y sus estados', () => {
    beforeEach(() => {
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el skeleton mientras carga', () => {
        vi.mocked(vehicleService.getAllVehicles).mockImplementation(() => new Promise<never>(() => {}));

        const { container } = renderPage();

        expect(container.querySelector('.animate-pulse')).not.toBeNull();
    });

    it('lista los vehículos que devuelve la API', async () => {
        vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(mockVehicles);

        renderPage();

        expect(await screen.findByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('Nissan Kicks')).toBeInTheDocument();
    });

    it('muestra el estado vacío del catálogo cuando no hay vehículos', async () => {
        vi.mocked(vehicleService.getAllVehicles).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Aún no hay vehículos registrados en el taller.')).toBeInTheDocument();
    });

    it('distingue el vacío por búsqueda del catálogo vacío', async () => {
        vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(mockVehicles);

        renderPage();
        await screen.findByText('Ford Fiesta');

        fireEvent.change(screen.getByRole('textbox', { name: 'Buscar por patente, marca o modelo' }), {
            target: { value: 'zzz' },
        });

        expect(await screen.findByText('No se encontraron vehículos para "zzz".')).toBeInTheDocument();
        expect(screen.queryByText('Aún no hay vehículos registrados en el taller.')).not.toBeInTheDocument();
    });

    it('muestra el banner offline con la caché cuando no hay respuesta del servidor', async () => {
        vi.mocked(vehicleService.getAllVehicles).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    });

    it('muestra un estado de error reintentable ante un error del servidor sin caché', async () => {
        vi.mocked(vehicleService.getAllVehicles).mockRejectedValue(axiosServerError);

        renderPage();

        expect(await screen.findByText('No se pudieron cargar los vehículos')).toBeInTheDocument();
        expect(screen.getByText('El servidor tuvo un problema. Intente más tarde.')).toBeInTheDocument();
        // El banner de "sin conexión" no debe usarse para un error del servidor.
        expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
    });

    it('reintenta la carga al pulsar el botón del estado de error', async () => {
        vi.mocked(vehicleService.getAllVehicles).mockRejectedValue(axiosServerError);

        renderPage();

        const reintentar = await screen.findByRole('button', { name: 'Reintentar' });
        vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(mockVehicles);
        fireEvent.click(reintentar);

        expect(await screen.findByText('Ford Fiesta')).toBeInTheDocument();
    });

    it('conserva la caché y avisa cuando el error del servidor ocurre con datos ya cargados', async () => {
        useVehicleStore.setState({ vehicles: mockVehicles, status: 'error', error: 'El servidor tuvo un problema. Intente más tarde.', isOffline: false });
        vi.mocked(vehicleService.getAllVehicles).mockRejectedValue(axiosServerError);

        renderPage();

        expect(await screen.findByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByRole('alert')).toHaveTextContent('El servidor tuvo un problema.');
    });
});
