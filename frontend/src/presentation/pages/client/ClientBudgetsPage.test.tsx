import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useBudgetStore } from '@/infrastructure/stores/useBudgetStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import {
    mockPresupuestoAprobado,
    mockPresupuestoPendiente,
} from '@/infrastructure/mocks/budgets.mock';
import { ClientBudgetsPage } from './ClientBudgetsPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
        getOrderById: vi.fn(),
        getOrderHistory: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        decidir: vi.fn(),
    },
}));

function servicio(id: string, estadoCodigo: number): Order {
    return {
        id,
        vehicleId: '1',
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: `2026-09-0${id.slice(-1)}T10:00:00`,
        patente: 'ABCD-12',
    };
}

const axiosNetworkError = { isAxiosError: true };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientBudgetsPage />
        </MemoryRouter>
    );
}

describe('ClientBudgetsPage: listado de presupuestos del cliente', () => {
    beforeEach(() => {
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false, requestId: null });
        useBudgetStore.setState({ presupuestos: [], status: 'idle', error: null, isOffline: false, requestId: null });
        useVehicleStore.setState({ vehicles: [], status: 'idle', error: null, isOffline: false });
        vi.clearAllMocks();
    });

    it('lista los presupuestos y destaca los pendientes de decisión', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([servicio('101', 3), servicio('102', 5)]);
        vi.mocked(presupuestoService.getByOrder).mockImplementation((ordenId) =>
            Promise.resolve(ordenId === '101' ? mockPresupuestoPendiente : mockPresupuestoAprobado)
        );

        renderPage();

        expect(await screen.findByText('Servicio n° 101')).toBeInTheDocument();
        expect(screen.getByText('Servicio n° 102')).toBeInTheDocument();
        expect(screen.getByText('Pendiente de su decisión')).toBeInTheDocument();
        expect(screen.getByText('Aprobado')).toBeInTheDocument();
        expect(screen.getByText('$108.000')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /Revisar y Aprobar/ })).toHaveAttribute(
            'href',
            '/client/presupuestos/101'
        );
        expect(screen.getByRole('link', { name: /Ver detalle/ })).toHaveAttribute(
            'href',
            '/client/presupuestos/102'
        );
    });

    it('no consulta presupuestos de órdenes que aún no llegan a esa etapa', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([servicio('101', 1), servicio('102', 2)]);
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(null);

        renderPage();

        expect(
            await screen.findByText('Aún no tiene presupuestos')
        ).toBeInTheDocument();
        expect(presupuestoService.getByOrder).not.toHaveBeenCalled();
    });

    it('muestra el estado vacío cuando no hay presupuestos', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([servicio('101', 3)]);
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(null);

        renderPage();

        expect(await screen.findByText('Aún no tiene presupuestos')).toBeInTheDocument();
    });

    it('un error del servidor sin caché lo muestra con ErrorState y reintento', async () => {
        vi.mocked(orderService.getOrders).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudieron cargar sus presupuestos')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    });

    it('queda offline y conserva la caché de presupuestos', async () => {
        useOrderStore.setState({ orders: [servicio('101', 3)], status: 'idle', error: null, isOffline: false });
        useBudgetStore.setState({
            presupuestos: [mockPresupuestoPendiente],
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.mocked(orderService.getOrders).mockRejectedValue(axiosNetworkError);
        vi.mocked(presupuestoService.getByOrder).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.getByText('Servicio n° 101')).toBeInTheDocument();
    });
});
