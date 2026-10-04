import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { MechanicStatusPage } from './MechanicStatusPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        cambiarEstado: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAssignedVehicles: vi.fn(),
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

// Identidad real de la sesión (usuario_id de MS1).
const MECANICO_ID = 'm1';
const ordEnReparacion = orden('101', 5);
const ordDeOtro = orden('102', 1, 'm2');
// Estado 7 (Entregado): no tiene ningún avance del mecánico.
const ordEntregada = orden('103', 7);

// Fallo de transporte: error Axios sin respuesta HTTP, así que isOfflineError
// lo clasifica como "sin conexión" (no como error del servidor).
const axiosNetworkError = { isAxiosError: true };

function renderPage() {
    return render(
        <MemoryRouter>
            <ToastProvider>
                <MechanicStatusPage />
            </ToastProvider>
        </MemoryRouter>
    );
}

describe('MechanicStatusPage: actualización de estados de las órdenes', () => {
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
        vi.mocked(vehicleService.getAssignedVehicles).mockResolvedValue([]);
    });

    it('muestra las órdenes asignadas con los avances disponibles para el estado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();

        expect(await screen.findByText('Actualizar Estados')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getAllByText('En reparación').length).toBeGreaterThan(0);
        const selector = screen.getByLabelText('Siguiente estado de la orden 101');
        expect(selector).toBeInTheDocument();
        // "Listo" también es una opción del filtro de estado, así que se acota al selector.
        expect(within(selector).getByRole('option', { name: 'Listo' })).toBeInTheDocument();
    });

    it('pide confirmación antes de avanzar y recién entonces llama a cambiarEstado', async () => {
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
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));

        // El diálogo aparece y todavía no se golpeó la API.
        expect(await screen.findByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/pasará de En reparación a Listo/)).toBeInTheDocument();
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));

        await waitFor(() =>
            expect(orderService.cambiarEstado).toHaveBeenCalledWith('101', 6, '')
        );
    });

    it('cancela el diálogo sin llamar a la API', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();
        await screen.findByText('Orden n° 101');

        fireEvent.change(screen.getByLabelText('Siguiente estado de la orden 101'), {
            target: { value: '6' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Confirmar avance/ }));
        await screen.findByRole('dialog');
        fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
        expect(orderService.cambiarEstado).not.toHaveBeenCalled();
    });

    it('confirma el avance, llama a cambiarEstado, actualiza la caché y avisa con un toast', async () => {
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
        await screen.findByRole('dialog');
        fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));

        await waitFor(() =>
            expect(orderService.cambiarEstado).toHaveBeenCalledWith('101', 6, 'Trabajo terminado')
        );
        expect(await screen.findByText(/Orden n° 101 actualizada a Listo/)).toBeInTheDocument();
    });

    it('mueve a órdenes cerradas las que no tienen avance del mecánico', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion, ordEntregada]);

        renderPage();

        expect(await screen.findByText('Órdenes cerradas')).toBeInTheDocument();
        expect(
            screen.getByText('No hay avances disponibles para el mecánico en este estado.')
        ).toBeInTheDocument();
        // La orden cerrada no ofrece selector de estado.
        expect(screen.queryByLabelText('Siguiente estado de la orden 103')).not.toBeInTheDocument();
        expect(screen.getByLabelText('Siguiente estado de la orden 101')).toBeInTheDocument();
    });

    it('filtra por estado desde la barra de herramientas', async () => {
        useOrderStore.setState({
            orders: [orden('101', 5), orden('102', 1)],
            status: 'success',
            error: null,
        });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        await screen.findByText('Orden n° 101');
        await screen.findByText('Orden n° 102');

        fireEvent.change(screen.getByLabelText('Filtrar por estado'), {
            target: { value: '1' },
        });

        expect(screen.queryByText('Orden n° 101')).not.toBeInTheDocument();
        expect(screen.getByText('Orden n° 102')).toBeInTheDocument();
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
        await screen.findByRole('dialog');
        fireEvent.click(screen.getByRole('button', { name: 'Avanzar estado' }));

        expect(await screen.findByRole('alert')).toHaveTextContent(
            'Transición no permitida: En reparación -> Listo'
        );
    });

    it('pagina las órdenes y respeta el tamaño de página elegido', async () => {
        // useOrderListFilters ordena por actualizadoEn descendente, así que cada
        // orden necesita su propia fecha para que la página sea determinista.
        const muchas = Array.from({ length: 8 }, (_, i) => ({
            ...orden(String(200 + i), 5),
            actualizadoEn: new Date(Date.UTC(2026, 0, 1 + i)).toISOString(),
        }));
        useOrderStore.setState({ orders: muchas, status: 'success', error: null });
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        // La más reciente encabeza la lista: la 207 y la 202 llenan la primera
        // página de 6; la 201 cae en la segunda.
        expect(await screen.findByText('Orden n° 207')).toBeInTheDocument();
        expect(screen.getByText('Orden n° 202')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 201')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));

        expect(await screen.findByText('Orden n° 201')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 207')).not.toBeInTheDocument();
    });

    it('offline acota la caché compartida a las órdenes del mecánico', async () => {
        useOrderStore.setState({ orders: [ordEnReparacion, ordDeOtro], isOffline: true });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.queryByText('Orden n° 102')).not.toBeInTheDocument();
    });
});