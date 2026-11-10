import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import type { User, UserRole } from '@/domain/entities/User';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { ClientNuevaAtencionDetailPage } from './ClientNuevaAtencionDetailPage';

// Simulaciones del contrato acordado (Entrega B); el backend B está pendiente.
vi.mock('@/infrastructure/api/NuevaAtencionService', () => ({
    nuevaAtencionService: { solicitar: vi.fn(), listar: vi.fn(), obtener: vi.fn() },
}));

const base: SolicitudNuevaAtencion = {
    id: '4',
    ordenCanceladaId: '25',
    vehiculoId: '9',
    clienteUsuarioId: '10',
    descripcion: 'Ruido al frenar',
    solicitadaEn: '2026-11-08T14:00:00-03:00',
    situacion: 'pendiente',
    respuesta: null,
    revisorId: null,
    revisadaEn: null,
    ordenGeneradaId: null,
};

function iniciar(roles: UserRole[], id = '10') {
    const user: User = { id, email: 'c@taller.cl', full_name: 'Cliente', role: roles[0], roles, is_active: true };
    useAuthStore.setState({ user, token: 't', isAuthenticated: true });
}

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/client/nuevas-atenciones/4']}>
            <Routes>
                <Route path="/client/nuevas-atenciones/:id" element={<ClientNuevaAtencionDetailPage />} />
            </Routes>
        </MemoryRouter>
    );

beforeEach(() => {
    vi.clearAllMocks();
    iniciar(['cliente']);
    useVehicleStore.setState({ vehicles: [] });
});

describe('ClientNuevaAtencionDetailPage', () => {
    it('pendiente: muestra los datos y que no reserva hora ni crea orden', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue(base);

        renderPage();

        expect(await screen.findByRole('heading', { name: 'Solicitud de nueva atención n° 4' })).toBeInTheDocument();
        expect(screen.getByText('Pendiente de revisión')).toBeInTheDocument();
        expect(screen.getByText('Ruido al frenar')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Orden n° 25' })).toHaveAttribute('href', '/client/ordenes/25');
        expect(screen.getByText(/No reserva una hora ni crea una orden/)).toBeInTheDocument();
        expect(nuevaAtencionService.obtener).toHaveBeenCalledWith('4');
    });

    it('rechazada: muestra la respuesta y permite solicitar de nuevo desde la orden cancelada', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue({
            ...base, situacion: 'rechazada', respuesta: 'Debe traer el vehículo primero', revisorId: '3',
            revisadaEn: '2026-11-08T15:00:00-03:00',
        });

        renderPage();

        expect(await screen.findByText('Debe traer el vehículo primero')).toBeInTheDocument();
        expect(screen.getByText('Rechazada')).toBeInTheDocument();
        expect(screen.getByText('3')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'orden cancelada n° 25' })).toHaveAttribute('href', '/client/ordenes/25');
    });

    it('aceptada con orden generada: enlaza a su detalle', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue({
            ...base, situacion: 'aceptada', respuesta: 'Lo esperamos', revisorId: '3',
            revisadaEn: '2026-11-08T15:00:00-03:00', ordenGeneradaId: '30',
        });

        renderPage();

        expect(await screen.findByRole('link', { name: 'Ver orden n° 30' })).toHaveAttribute('href', '/client/ordenes/30');
        expect(screen.getByText('Aceptada')).toBeInTheDocument();
    });

    it('aceptada sin orden generada: no la inventa', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue({
            ...base, situacion: 'aceptada', respuesta: 'Lo esperamos', revisorId: '3', revisadaEn: '2026-11-08T15:00:00-03:00',
        });

        renderPage();

        expect(await screen.findByText('Aún no hay una orden generada para esta solicitud.')).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /Ver orden n°/ })).not.toBeInTheDocument();
    });

    it('cuenta con Administrador viendo la solicitud de otro cliente: enlaza al detalle administrativo', async () => {
        iniciar(['cliente', 'administrador'], '3');
        vi.mocked(nuevaAtencionService.obtener).mockResolvedValue({ ...base, situacion: 'aceptada', ordenGeneradaId: '30' });

        renderPage();

        expect(await screen.findByRole('link', { name: 'Ver orden n° 30' })).toHaveAttribute('href', '/admin/ordenes/30');
        expect(screen.getByRole('link', { name: 'Orden n° 25' })).toHaveAttribute('href', '/admin/ordenes/25');
    });

    it('404: inexistente o ajena', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockRejectedValue({ isAxiosError: true, response: { status: 404, data: { detail: 'Solicitud no encontrada' } } });

        renderPage();

        expect(await screen.findByText('Solicitud no encontrada.')).toBeInTheDocument();
    });

    it('otro error se muestra con su detail', async () => {
        vi.mocked(nuevaAtencionService.obtener).mockRejectedValue({ isAxiosError: true, response: { status: 403, data: { detail: 'Se requiere el rol Cliente o Administrador' } } });

        renderPage();

        expect(await screen.findByText('Se requiere el rol Cliente o Administrador')).toBeInTheDocument();
    });
});
