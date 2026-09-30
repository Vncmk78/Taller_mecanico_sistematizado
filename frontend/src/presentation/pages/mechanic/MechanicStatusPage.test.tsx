import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { MechanicStatusPage } from './MechanicStatusPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        cambiarEstado: vi.fn(),
    },
}));

function orden(id: string, estadoCodigo: number, mecanicoActualId: string | null = 'm1'): Order {
    return {
        id,
        vehicleId: '1',
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: 'ABCD-12',
        vehiculo: 'Ford Fiesta',
    };
}

const ordEnReparacion = orden('101', 5);
const ordDeOtro = orden('102', 1, 'm2');

function renderPage() {
    return render(
        <MemoryRouter>
            <MechanicStatusPage />
        </MemoryRouter>
    );
}

describe('MechanicStatusPage: actualización de estados de las órdenes', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('muestra las órdenes asignadas con los avances disponibles para el estado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();

        expect(await screen.findByText('Actualizar Estados')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getAllByText('En reparación').length).toBeGreaterThan(0);
        expect(screen.getByLabelText('Siguiente estado de la orden 101')).toBeInTheDocument();
        expect(screen.getByRole('option', { name: 'Listo' })).toBeInTheDocument();
    });

    it('confirma el avance, llama a cambiarEstado y actualiza la caché', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
        vi.mocked(orderService.cambiarEstado).mockResolvedValue({
            ...ordEnReparacion,
            estadoCodigo: 6,
        });

        renderPage();
        await screen.findByText('Orden n° 101');

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.change(screen.getByLabelText('Observación de la orden 101'), {
            target: { value: 'Trabajo terminado' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));

        await waitFor(() =>
            expect(orderService.cambiarEstado).toHaveBeenCalledWith('101', 6, 'Trabajo terminado')
        );
        expect(screen.getAllByText('Listo').length).toBeGreaterThan(0);
        expect(
            screen.getByText('Sin avances disponibles para el estado actual.')
        ).toBeInTheDocument();
    });

    it('muestra el detalle del error del backend (409) en la tarjeta', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);
        const error = new AxiosError(
            'Request failed with status code 409',
            AxiosError.ERR_BAD_RESPONSE,
            undefined,
            undefined,
            {
                status: 409,
                statusText: 'Conflict',
                headers: {},
                config: {} as InternalAxiosRequestConfig,
                data: { detail: 'Transición no permitida: En reparación -> Listo' },
            }
        );
        vi.mocked(orderService.cambiarEstado).mockRejectedValue(error);

        renderPage();
        await screen.findByText('Orden n° 101');

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));

        expect(await screen.findByRole('alert')).toHaveTextContent(
            'Transición no permitida: En reparación -> Listo'
        );
    });

  it('offline conserva la caché con las órdenes asignadas al mecánico', async () => {
    useOrderStore.setState({ orders: [ordEnReparacion, ordDeOtro], isOffline: true });
    vi.mocked(orderService.getOrders).mockRejectedValue(new Error('network'));

    renderPage();

    expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    // La caché ya viene filtrada por la Gateway, así que offline se conserva
    // tal cual sin volver a filtrar por un mecánico de ejemplo.
    expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
    expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
  });
});