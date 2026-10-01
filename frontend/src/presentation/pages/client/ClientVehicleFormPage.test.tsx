import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { errorAxios, errorInternoGateway, gatewaySaturada, patenteDuplicada } from '@/infrastructure/mocks/payloads.reales';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientVehicleFormPage } from './ClientVehicleFormPage';

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getMyVehicles: vi.fn(),
        getAllVehicles: vi.fn(),
        getAssignedVehicles: vi.fn(),
        getVehicleById: vi.fn(),
        createVehicle: vi.fn(),
    },
}));

const CLIENTE_ID = '7';

// Datos válidos según el contrato de MS2: la patente solo exige
// `min_length=1` (sin patrón) y marca/modelo admiten hasta 60 caracteres.
const DATOS = {
    patent: 'ZZZZ11',
    brand: 'Toyota',
    model: 'Corolla',
    year: '2018',
    mileage: '45000',
};

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/vehiculos/nuevo']}>
            <Routes>
                <Route path="/client/vehiculos/nuevo" element={<ClientVehicleFormPage />} />
                <Route path="/client/vehiculos" element={<p>Listado de vehículos</p>} />
            </Routes>
        </MemoryRouter>
    );
}

function completarFormulario() {
    fireEvent.change(screen.getByLabelText(/Patente/), { target: { value: DATOS.patent } });
    fireEvent.change(screen.getByLabelText(/Marca/), { target: { value: DATOS.brand } });
    fireEvent.change(screen.getByLabelText(/Modelo/), { target: { value: DATOS.model } });
    fireEvent.change(screen.getByLabelText(/Año/), { target: { value: DATOS.year } });
    fireEvent.change(screen.getByLabelText(/Kilometraje actual/), { target: { value: DATOS.mileage } });
}

describe('ClientVehicleFormPage: errores reales del backend al registrar', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: CLIENTE_ID,
                email: 'ana@correo.cl',
                full_name: 'Ana Pérez',
                role: 'cliente',
                is_active: true,
            },
        });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra el mensaje real de MS2 cuando la patente ya está registrada (409)', async () => {
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(errorAxios(409, patenteDuplicada));

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        // El 409 real trae este literal; la UI lo muestra en el campo patente
        // en vez de un texto propio, para que el motivo sea el del servidor.
        expect(await screen.findByText('La patente ya está registrada')).toBeInTheDocument();
        // Y no cae en el error genérico del formulario.
        expect(screen.queryByText(/No pudimos registrar el vehículo/)).not.toBeInTheDocument();
    });

    it('muestra el mensaje real de la Gateway ante un 500 con su reference', async () => {
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(errorAxios(500, errorInternoGateway));

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('Ocurrió un error inesperado en la Gateway.')).toBeInTheDocument();
        // El request_id permite rastrear el fallo en los logs del backend.
        expect(screen.getByText(/Referencia: 9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8/)).toBeInTheDocument();
    });

    it('propaga el mensaje de saturación de la Gateway (503) sin inventar otro texto', async () => {
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(errorAxios(503, gatewaySaturada));

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('La Gateway está ocupada. Intente más tarde.')).toBeInTheDocument();
    });

    it('omite la referencia cuando el error no trae request_id', async () => {
        // Un 422 de validación de FastAPI no lleva request_id: no hay nada que
        // rastrear, así que no se muestra una referencia inventada.
        vi.mocked(vehicleService.createVehicle).mockRejectedValue(
            errorAxios(422, { detail: [{ loc: ['body', 'patente'], msg: 'String should have at least 1 character' }] })
        );

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('String should have at least 1 character')).toBeInTheDocument();
        expect(screen.queryByText(/Referencia:/)).not.toBeInTheDocument();
    });

    it('registra el vehículo y vuelve al listado cuando la Gateway responde bien', async () => {
        vi.mocked(vehicleService.createVehicle).mockResolvedValue({
            id: '12',
            patent: 'ZZZZ11',
            brand: 'Toyota',
            model: 'Corolla',
            year: 2018,
            mileage: 45000,
            clientId: CLIENTE_ID,
        });

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        await waitFor(() => expect(screen.getByText('Listado de vehículos')).toBeInTheDocument());
        expect(vehicleService.createVehicle).toHaveBeenCalledWith({
            patent: 'ZZZZ11',
            brand: 'Toyota',
            model: 'Corolla',
            year: 2018,
            mileage: 45000,
        });
    });

    it('no llama a la Gateway si el propio formulario ya detecta la patente repetida', async () => {
        // Verificación optimista: evita un viaje de ida y vuelta cuando el
        // duplicado ya está en la caché local.
        useVehicleStore.setState({
            vehicles: [
                { id: '12', patent: 'ZZZZ11', brand: 'Toyota', model: 'Corolla', year: 2018, mileage: 45000, clientId: CLIENTE_ID },
            ],
        });

        renderPage();
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('Ya existe un vehículo registrado con esa patente.')).toBeInTheDocument();
        expect(vehicleService.createVehicle).not.toHaveBeenCalled();
    });
});

// Estas pruebas fijan que el formulario respete lo que declara el contrato de
// MS2 (gateway/contratos/vehiculos.py). Antes el formulario era más restrictivo
// que el servidor: exigía un patrón de patente que el contrato no define y no
// ponía el tope de 60 caracteres que el backend sí impone.
describe('ClientVehicleFormPage: el formulario sigue el contrato de MS2', () => {
    beforeEach(() => {
        useAuthStore.setState({
            user: {
                id: CLIENTE_ID,
                email: 'ana@correo.cl',
                full_name: 'Ana Pérez',
                role: 'cliente',
                is_active: true,
            },
        });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('acepta la patente del ejemplo del contrato, que no lleva guion', async () => {
        // "AB1234" es el ejemplo de gateway/contratos/vehiculos.py y el test de
        // MS2 afirma que el contrato no define patrón. Antes el formulario lo
        // rechazaba por exigir 4 letras, guion y 2 dígitos.
        vi.mocked(vehicleService.createVehicle).mockResolvedValue({
            id: '12',
            patent: 'AB1234',
            brand: 'Toyota',
            model: 'Corolla',
            year: 2018,
            mileage: 45000,
            clientId: CLIENTE_ID,
        });

        renderPage();
        fireEvent.change(screen.getByLabelText(/Patente/), { target: { value: 'AB1234' } });
        fireEvent.change(screen.getByLabelText(/Marca/), { target: { value: 'Toyota' } });
        fireEvent.change(screen.getByLabelText(/Modelo/), { target: { value: 'Corolla' } });
        fireEvent.change(screen.getByLabelText(/Año/), { target: { value: '2018' } });
        fireEvent.change(screen.getByLabelText(/Kilometraje actual/), { target: { value: '45000' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        await waitFor(() => expect(vehicleService.createVehicle).toHaveBeenCalled());
        expect(vehicleService.createVehicle).toHaveBeenCalledWith(
            expect.objectContaining({ patent: 'AB1234' })
        );
    });

    it('bloquea en el cliente una marca de más de 60 caracteres, que el backend rechazaría con 422', async () => {
        // El 422 real del servidor está en payloads.reales.ts
        // (textoVehiculoDemasiadoLargo). Sin este tope, la UI aceptaba el texto
        // largo y el usuario recibía el rechazo del servidor.
        renderPage();
        fireEvent.change(screen.getByLabelText(/Patente/), { target: { value: 'AB1234' } });
        fireEvent.change(screen.getByLabelText(/Marca/), { target: { value: 'T'.repeat(61) } });
        fireEvent.change(screen.getByLabelText(/Modelo/), { target: { value: 'Corolla' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        expect(await screen.findByText('La marca no puede superar 60 caracteres')).toBeInTheDocument();
        expect(vehicleService.createVehicle).not.toHaveBeenCalled();
    });

    it('registra sin año ni kilometraje y los envía en null, que es lo que admite el contrato', async () => {
        // `anio` y `kilometraje` son opcionales (int | None). Antes eran
        // obligatorios y además exigían un rango que el contrato no declara.
        vi.mocked(vehicleService.createVehicle).mockResolvedValue({
            id: '13',
            patent: 'CD5678',
            brand: 'Hyundai',
            model: 'Accent',
            year: 0,
            mileage: 0,
            clientId: CLIENTE_ID,
        });

        renderPage();
        fireEvent.change(screen.getByLabelText(/Patente/), { target: { value: 'CD5678' } });
        fireEvent.change(screen.getByLabelText(/Marca/), { target: { value: 'Hyundai' } });
        fireEvent.change(screen.getByLabelText(/Modelo/), { target: { value: 'Accent' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        await waitFor(() => expect(vehicleService.createVehicle).toHaveBeenCalled());
        expect(vehicleService.createVehicle).toHaveBeenCalledWith({
            patent: 'CD5678',
            brand: 'Hyundai',
            model: 'Accent',
            year: null,
            mileage: null,
        });
    });

    it('acepta un kilometraje por sobre el antiguo tope de 999999, porque el contrato no lo acota', async () => {
        vi.mocked(vehicleService.createVehicle).mockResolvedValue({
            id: '14',
            patent: 'EF9012',
            brand: 'Mitsubishi',
            model: 'L200',
            year: 1995,
            mileage: 1500000,
            clientId: CLIENTE_ID,
        });

        renderPage();
        fireEvent.change(screen.getByLabelText(/Patente/), { target: { value: 'EF9012' } });
        fireEvent.change(screen.getByLabelText(/Marca/), { target: { value: 'Mitsubishi' } });
        fireEvent.change(screen.getByLabelText(/Modelo/), { target: { value: 'L200' } });
        fireEvent.change(screen.getByLabelText(/Año/), { target: { value: '1995' } });
        fireEvent.change(screen.getByLabelText(/Kilometraje actual/), { target: { value: '1500000' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar Vehículo' }));

        await waitFor(() => expect(vehicleService.createVehicle).toHaveBeenCalled());
        expect(vehicleService.createVehicle).toHaveBeenCalledWith(
            expect.objectContaining({ year: 1995, mileage: 1500000 })
        );
    });
});
