import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { CupoDiarioIngresos } from '@/domain/entities/ConfiguracionTaller';
import type { Order } from '@/domain/entities/Order';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { configuracionTallerService } from '@/infrastructure/api/ConfiguracionTallerService';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { RegistrarIngresoPanel } from './RegistrarIngresoPanel';

vi.mock('@/infrastructure/api/OrderService', () => ({ orderService: { crearOrden: vi.fn() } }));
vi.mock('@/infrastructure/api/VehicleService', () => ({ vehicleService: { getAllVehicles: vi.fn() } }));
vi.mock('@/infrastructure/api/ConfiguracionTallerService', () => ({
    configuracionTallerService: { obtenerCupoDiario: vi.fn() },
}));

const VEHICULOS: Vehicle[] = [
    { id: '1', patent: 'ABCD12', brand: 'Toyota', model: 'Yaris', year: 2020, mileage: 0, clientId: '7' },
    { id: '2', patent: 'WXYZ34', brand: 'Kia', model: 'Rio', year: 2019, mileage: 0, clientId: '8' },
];

const cupo = (over: Partial<CupoDiarioIngresos> = {}): CupoDiarioIngresos => ({
    maxIngresosDiarios: 10,
    actualizadoPorId: '1',
    actualizadoEn: '2026-11-07T09:00:00-03:00',
    jornadaLocal: '2026-11-07',
    ingresosRegistrados: 3,
    sobreLimite: false,
    ...over,
});

const ordenCreada: Order = {
    id: '55', vehicleId: '2', ingresoId: 40, estadoCodigo: 1, mecanicoActualId: null,
    creadoPorId: '1', creadoEn: '2026-11-07T10:00:00-03:00', actualizadoEn: '2026-11-07T10:00:00-03:00',
};

function error409(detail: string): AxiosError {
    const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
    return new AxiosError('409', '409', config, undefined, {
        status: 409, statusText: '', headers: {}, config, data: { detail },
    });
}

function renderPanel(vehiculo?: Vehicle) {
    return render(
        <MemoryRouter initialEntries={['/admin/ordenes']}>
            <ToastProvider>
                <Routes>
                    <Route path="/admin/ordenes" element={<RegistrarIngresoPanel vehiculo={vehiculo} />} />
                    <Route path="/admin/ordenes/:id" element={<div>Detalle de la orden</div>} />
                </Routes>
            </ToastProvider>
        </MemoryRouter>
    );
}

async function crearDesdeSelector(id = '2') {
    fireEvent.change(await screen.findByLabelText('Vehículo registrado'), { target: { value: id } });
    fireEvent.click(screen.getByRole('button', { name: 'Registrar ingreso y crear orden' }));
    const dialog = await screen.findByRole('dialog', { name: '¿Registrar el ingreso y crear la orden?' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Crear orden' }));
}

beforeEach(() => {
    vi.clearAllMocks();
    useOrderStore.getState().reset();
    vi.mocked(vehicleService.getAllVehicles).mockResolvedValue(VEHICULOS);
    vi.mocked(configuracionTallerService.obtenerCupoDiario).mockResolvedValue(cupo());
});

describe('RegistrarIngresoPanel: ingreso físico y creación de orden', () => {
    it('lista los vehículos registrados e informa el uso del cupo', async () => {
        renderPanel();

        expect(await screen.findByRole('option', { name: 'WXYZ34 · Kia Rio' })).toBeInTheDocument();
        expect(await screen.findByText(/Ingresos de hoy:/)).toHaveTextContent('Ingresos de hoy: 3 de 10.');
        expect(screen.getByRole('button', { name: 'Registrar ingreso y crear orden' })).toBeDisabled();
    });

    it('crea la orden solo tras confirmar, la guarda y abre su detalle para asignar', async () => {
        vi.mocked(orderService.crearOrden).mockResolvedValue(ordenCreada);
        renderPanel();

        fireEvent.change(await screen.findByLabelText('Vehículo registrado'), { target: { value: '2' } });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar ingreso y crear orden' }));
        expect(orderService.crearOrden).not.toHaveBeenCalled();
        expect(screen.getByText(/cuenta para el cupo del día aunque la orden se cancele/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Crear orden' }));

        expect(await screen.findByText('Detalle de la orden')).toBeInTheDocument();
        expect(orderService.crearOrden).toHaveBeenCalledTimes(1);
        expect(orderService.crearOrden).toHaveBeenCalledWith('2');
        expect(useOrderStore.getState().orders.map((o) => o.id)).toEqual(['55']);
    });

    it.each([
        'El taller ya alcanzó el máximo diario de ingresos físicos',
        'Configura el máximo diario de ingresos físicos antes de recibir vehículos',
    ])('muestra el rechazo de MS2 (%s) sin guardar nada', async (detalle) => {
        vi.mocked(orderService.crearOrden).mockRejectedValue(error409(detalle));
        renderPanel();

        await crearDesdeSelector();

        expect(await screen.findByText(detalle)).toBeInTheDocument();
        expect(useOrderStore.getState().orders).toEqual([]);
        expect(screen.queryByText('Detalle de la orden')).not.toBeInTheDocument();
    });

    it('avisa cuando el cupo no está configurado y enlaza a la configuración', async () => {
        vi.mocked(configuracionTallerService.obtenerCupoDiario).mockResolvedValue(
            cupo({ maxIngresosDiarios: null })
        );
        renderPanel();

        expect(await screen.findByRole('link', { name: 'Configurarlo' })).toHaveAttribute(
            'href', '/admin/configuracion'
        );
    });

    it('con el vehículo de la ficha no pide elegirlo y no consulta la lista', async () => {
        vi.mocked(orderService.crearOrden).mockResolvedValue({ ...ordenCreada, vehicleId: '1' });
        renderPanel(VEHICULOS[0]);

        expect(screen.getByText('ABCD12 · Toyota Yaris')).toBeInTheDocument();
        expect(screen.queryByLabelText('Vehículo registrado')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Registrar ingreso y crear orden' }));
        fireEvent.click(await screen.findByRole('button', { name: 'Crear orden' }));

        await waitFor(() => expect(orderService.crearOrden).toHaveBeenCalledWith('1'));
        expect(vehicleService.getAllVehicles).not.toHaveBeenCalled();
    });

    it('un doble clic en confirmar crea una sola orden', async () => {
        let resolver: (o: Order) => void = () => {};
        vi.mocked(orderService.crearOrden).mockImplementation(() => new Promise((r) => (resolver = r)));
        renderPanel(VEHICULOS[0]);

        fireEvent.click(screen.getByRole('button', { name: 'Registrar ingreso y crear orden' }));
        const confirmar = await screen.findByRole('button', { name: 'Crear orden' });
        fireEvent.click(confirmar);
        fireEvent.click(confirmar);
        resolver(ordenCreada);

        expect(await screen.findByText('Detalle de la orden')).toBeInTheDocument();
        expect(orderService.crearOrden).toHaveBeenCalledTimes(1);
    });
});
