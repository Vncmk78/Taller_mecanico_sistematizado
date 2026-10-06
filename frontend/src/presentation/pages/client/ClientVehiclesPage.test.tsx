import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { errorAxios, errorInternoGateway, gatewaySaturada } from '@/infrastructure/mocks/payloads.reales';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientVehiclesPage } from './ClientVehiclesPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAllVehicles: vi.fn(),
        getMyVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
    },
}));

function vehiculo(id: string, patent: string, model: string, clientId: string): Vehicle {
    return { id, patent, brand: 'Ford', model, year: 2020, mileage: 10000, clientId };
}

// Identidad real de la sesión (usuario_id de MS1): los vehículos del cliente c1
// son los que devuelve la Gateway, la vista no inventa el resto.
const CLIENTE_ID = 'c1';
const mio1 = vehiculo('1', 'ABCD-12', 'Fiesta', CLIENTE_ID);
const mio2 = vehiculo('6', 'QWER-12', 'Spark', CLIENTE_ID);
const deOtro = vehiculo('2', 'EFGH-34', 'Kicks', 'c2');

const axiosNetworkError = { isAxiosError: true };
const axiosServerError = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientVehiclesPage />
        </MemoryRouter>
    );
}

describe('ClientVehiclesPage: mis vehículos y sus estados', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: CLIENTE_ID,
                email: 'cliente@ taller.cl',
                full_name: 'Cliente Prueba',
                role: 'cliente',
                is_active: true,
            },
        });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el skeleton mientras carga', () => {
        vi.mocked(vehicleService.getMyVehicles).mockImplementation(() => new Promise<never>(() => {}));

        const { container } = renderPage();

        expect(container.querySelector('.animate-pulse')).not.toBeNull();
    });

    it('lista solo los vehículos del cliente autenticado', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockResolvedValue([mio1, mio2, deOtro]);

        renderPage();

        expect(await screen.findByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('Ford Spark')).toBeInTheDocument();
        // La pertenencia se resuelve con el clientId real de la sesión.
        expect(screen.queryByText('Ford Kicks')).not.toBeInTheDocument();
    });

    it('muestra el estado vacío con acción de registro cuando no hay vehículos', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Aún no tiene vehículos registrados.')).toBeInTheDocument();
        expect(
            screen.getAllByRole('link', { name: /Registrar vehículo/ }).length
        ).toBeGreaterThan(0);
    });

    it('distingue el vacío por búsqueda del catálogo vacío', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockResolvedValue([mio1, mio2]);

        renderPage();
        await screen.findByText('Ford Fiesta');

        fireEvent.change(screen.getByRole('textbox', { name: 'Buscar por patente, marca o modelo' }), {
            target: { value: 'zzz' },
        });

        expect(await screen.findByText('No se encontraron vehículos para "zzz".')).toBeInTheDocument();
    });

    it('muestra el banner offline cuando no hay respuesta del servidor', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    });

    it('muestra un estado de error reintentable ante un error del servidor sin caché', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(axiosServerError);

        renderPage();

        expect(await screen.findByText('No se pudieron cargar sus vehículos')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
        expect(screen.queryByText(/No se pudo conectar con el servidor/)).not.toBeInTheDocument();
    });

    it('reintenta la carga al pulsar el botón del estado de error', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(axiosServerError);

        renderPage();

        const reintentar = await screen.findByRole('button', { name: 'Reintentar' });
        vi.mocked(vehicleService.getMyVehicles).mockResolvedValue([mio1]);
        fireEvent.click(reintentar);

        expect(await screen.findByText('Ford Fiesta')).toBeInTheDocument();
    });
});

// Cuerpos literales de la Gateway: el objetivo es que la vista clasifique y
// muestre lo que el backend envía de verdad, no un error genérico inventado.
describe('ClientVehiclesPage: clasificación con el cuerpo real de error de la Gateway', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: CLIENTE_ID,
                email: 'cliente@ taller.cl',
                full_name: 'Cliente Prueba',
                role: 'cliente',
                is_active: true,
            },
        });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('un 500 de la Gateway es un error del servidor, no un falso "no encontrado"', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(errorAxios(500, errorInternoGateway));

        renderPage();

        expect(await screen.findByText('No se pudieron cargar sus vehículos')).toBeInTheDocument();
        expect(screen.getByText('Ocurrió un error inesperado en la Gateway.')).toBeInTheDocument();
        // Con 500 no hay nada confirmado, así que no se afirma que no existan
        // vehículos: se ofrece reintentar.
        expect(screen.queryByText('Aún no tiene vehículos registrados.')).not.toBeInTheDocument();
    });

    it('muestra el request_id de la Gateway para rastrear el fallo', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(errorAxios(500, errorInternoGateway));

        renderPage();

        expect(await screen.findByText(/Referencia: 9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8/)).toBeInTheDocument();
    });

    it('un 503 se informa como fallo de servicio y muestra el mensaje real de la Gateway', async () => {
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(errorAxios(503, gatewaySaturada));

        renderPage();

        // 503 es indisponibilidad del servicio: se conserva la caché local y se
        // rotula como aviso de servicio caído, con el texto del backend.
        expect(await screen.findByText(/La Gateway está ocupada\. Intente más tarde\./)).toBeInTheDocument();
        expect(screen.getByText(/Mostrando datos disponibles localmente/)).toBeInTheDocument();
    });

    it('no inventa una referencia cuando el microservicio devuelve el error sin ella', async () => {
        // Un 500 manejado por MS2 llega como { detail } sin bloque error ni
        // cabecera X-Request-ID: se muestra el mensaje y nada más.
        vi.mocked(vehicleService.getMyVehicles).mockRejectedValue(
            errorAxios(500, { detail: 'No fue posible consultar los vehículos' })
        );

        renderPage();

        expect(await screen.findByText('No fue posible consultar los vehículos')).toBeInTheDocument();
        expect(screen.queryByText(/Referencia:/)).not.toBeInTheDocument();
    });
});
