import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { orderService } from '@/infrastructure/api/OrderService';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { MechanicDashboardPage } from './MechanicDashboardPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getOrders: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/VehicleService', () => ({
    vehicleService: {
        getAssignedVehicles: vi.fn(),
    },
}));

function orden(id: string, estadoCodigo: number, vehicleId: string, mecanicoActualId: string): Order {
    return {
        id,
        vehicleId,
        ingresoId: Number(id),
        estadoCodigo,
        mecanicoActualId,
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:00:00',
        actualizadoEn: '2026-09-05T16:30:00',
    };
}

const MECANICO_ID = 'm1';
const ordRecibida = orden('101', 1, '1', MECANICO_ID);
const ordEnReparacion = orden('102', 5, '2', MECANICO_ID);
const ordEntregada = orden('103', 7, '1', MECANICO_ID);
const ordDeOtro = orden('104', 5, '3', 'm2');

function renderPage() {
    return render(
        <MemoryRouter>
            <MechanicDashboardPage />
        </MemoryRouter>
    );
}

describe('MechanicDashboardPage: panel con indicadores del mecánico', () => {
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
        vi.mocked(vehicleService.getAssignedVehicles).mockResolvedValue([
            { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 85120, clientId: 'c1' },
            { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Kicks', year: 2021, mileage: 32500, clientId: 'c2' },
        ]);
    });

    it('calcula los indicadores sobre las órdenes del mecánico autenticado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([
            ordRecibida,
            ordEnReparacion,
            ordEntregada,
            ordDeOtro,
        ]);

        renderPage();

        expect(await screen.findByText('Órdenes asignadas')).toBeInTheDocument();
        // 4 órdenes llegan de la API pero solo 3 son del mecánico.
        const indicadores = screen.getByText('Órdenes asignadas').closest('div')?.parentElement;
        expect(indicadores).toHaveTextContent('3');
        expect(screen.getByText('Órdenes activas')).toBeInTheDocument();
        // Recibido (1) y En reparación (5) son las dos que el mecánico puede avanzar.
        expect(screen.getByText('Esperan tu avance')).toBeInTheDocument();
        expect(screen.getByText('Vehículos asignados')).toBeInTheDocument();
    });

    it('avisa cuántas órdenes esperan un avance del mecánico', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();

        expect(await screen.findByText('1 orden espera tu avance.')).toBeInTheDocument();
    });

    it('indica que no hay avances pendientes cuando ninguna orden es accionable', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEntregada]);

        renderPage();

        expect(await screen.findByText('No tienes avances pendientes por ahora.')).toBeInTheDocument();
    });

    it('muestra el desglose por estado', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordRecibida, ordEnReparacion]);

        renderPage();

        expect(await screen.findByText('Órdenes por estado')).toBeInTheDocument();
        expect(screen.getByText('Recibido')).toBeInTheDocument();
        expect(screen.getByText('En reparación')).toBeInTheDocument();
        // Sin órdenes en ese estado no se lista la fila.
        expect(screen.queryByText('Cancelado')).not.toBeInTheDocument();
    });

    it('muestra el estado vacío cuando no tiene órdenes asignadas', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([]);

        renderPage();

        expect(
            await screen.findByText('No tiene órdenes asignadas por el momento.')
        ).toBeInTheDocument();
    });

    it('enlaza a las pantallas de estados y de órdenes', async () => {
        vi.mocked(orderService.getOrders).mockResolvedValue([ordEnReparacion]);

        renderPage();

        expect(await screen.findByText('Actualizar estados')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /Actualizar estados/ })).toHaveAttribute(
            'href',
            '/mechanic/estados'
        );
        expect(screen.getByRole('link', { name: /Mis órdenes/ })).toHaveAttribute(
            'href',
            '/mechanic/ordenes'
        );
    });

    it('un error del servidor sin caché muestra el estado de error', async () => {
        vi.mocked(orderService.getOrders).mockRejectedValue({
            isAxiosError: true,
            response: { status: 500, data: {} },
        });

        renderPage();

        expect(await screen.findByText('No se pudieron cargar tus órdenes')).toBeInTheDocument();
    });
});