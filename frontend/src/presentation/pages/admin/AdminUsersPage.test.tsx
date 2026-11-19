import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { UsuarioListado } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { errorAxios } from '@/infrastructure/mocks/payloads.reales';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { AdminUsersPage } from './AdminUsersPage';

vi.mock('@/infrastructure/api/AuthService', () => ({
    authService: {
        listarUsuarios: vi.fn(),
        asignarRol: vi.fn(),
        retirarRol: vi.fn(),
    },
}));

const ADMIN: UsuarioListado = {
    id: '3',
    email: 'admin@taller.cl',
    full_name: 'Admin Principal',
    roles: ['administrador'],
    is_active: true,
};

const ANA: UsuarioListado = {
    id: '7',
    email: 'ana@correo.cl',
    full_name: 'Ana Pérez',
    roles: ['cliente'],
    is_active: true,
};

const MARTIN: UsuarioListado = {
    id: '42',
    email: 'martin@correo.cl',
    full_name: 'Martín Herrera',
    roles: ['mecanico'],
    is_active: true,
};

function renderPage() {
    return render(
        <ToastProvider>
            <AdminUsersPage />
        </ToastProvider>
    );
}

function filaDe(nombre: string): HTMLElement {
    return screen.getByText(nombre).closest('tr') as HTMLElement;
}

describe('AdminUsersPage: gestión de roles de las cuentas', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuthStore.setState({
            user: {
                id: '3',
                email: 'admin@taller.cl',
                full_name: 'Admin Principal',
                role: 'administrador',
                roles: ['administrador'],
                is_active: true,
            },
            token: 't',
            isAuthenticated: true,
        });
        vi.mocked(authService.listarUsuarios).mockResolvedValue([ADMIN, ANA, MARTIN]);
    });

    it('lista las cuentas con sus roles y bloquea la edición de la propia cuenta', async () => {
        renderPage();

        expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
        expect(screen.getByText('Cliente')).toBeInTheDocument();
        expect(screen.getByText('Mecánico')).toBeInTheDocument();
        expect(screen.getAllByText('Administrador').length).toBeGreaterThan(0);
        expect(within(filaDe('Admin Principal')).getByText('(su cuenta)')).toBeInTheDocument();
        expect(
            within(filaDe('Admin Principal')).getByRole('button', { name: 'Editar roles' })
        ).toBeDisabled();
        expect(
            within(filaDe('Ana Pérez')).getByRole('button', { name: 'Editar roles' })
        ).toBeEnabled();
    });

    it('asigna y retira roles con los endpoints idempotentes y refleja la respuesta', async () => {
        vi.mocked(authService.asignarRol).mockResolvedValue({
            ...ANA,
            roles: ['cliente', 'mecanico'],
        });
        vi.mocked(authService.retirarRol).mockResolvedValue({
            ...ANA,
            roles: ['mecanico'],
        });

        renderPage();

        await screen.findByText('Ana Pérez');
        fireEvent.click(
            within(filaDe('Ana Pérez')).getByRole('button', { name: 'Editar roles' })
        );

        expect(screen.getByRole('heading', { name: 'Roles de Ana Pérez' })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('checkbox', { name: 'Cliente' }));
        fireEvent.click(screen.getByRole('checkbox', { name: 'Mecánico' }));
        fireEvent.click(screen.getByRole('button', { name: 'Guardar roles' }));

        await waitFor(() =>
            expect(authService.asignarRol).toHaveBeenCalledWith('7', 'mecanico')
        );
        expect(authService.retirarRol).toHaveBeenCalledWith('7', 'cliente');
        expect(await screen.findByText('Roles de Ana Pérez actualizados.')).toBeInTheDocument();
        expect(within(filaDe('Ana Pérez')).getByText('Mecánico')).toBeInTheDocument();
        expect(within(filaDe('Ana Pérez')).queryByText('Cliente')).not.toBeInTheDocument();
    });

    it('advierte y pide confirmación antes de dejar una cuenta sin roles', async () => {
        vi.mocked(authService.retirarRol).mockResolvedValue({ ...MARTIN, roles: [] });

        renderPage();

        await screen.findByText('Martín Herrera');
        fireEvent.click(
            within(filaDe('Martín Herrera')).getByRole('button', { name: 'Editar roles' })
        );

        fireEvent.click(screen.getByRole('checkbox', { name: 'Mecánico' }));

        expect(
            screen.getByText(
                'Sin roles, esta cuenta no podrá acceder a ningún portal del sistema.'
            )
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Guardar roles' }));

        expect(authService.retirarRol).not.toHaveBeenCalled();
        const dialogo = await screen.findByRole('dialog');
        expect(
            within(dialogo).getByText(/no podrá acceder a ningún portal del sistema hasta que un administrador/)
        ).toBeInTheDocument();

        fireEvent.click(within(dialogo).getByRole('button', { name: 'Guardar sin roles' }));

        await waitFor(() =>
            expect(authService.retirarRol).toHaveBeenCalledWith('42', 'mecanico')
        );
        expect(within(filaDe('Martín Herrera')).getByText('Sin roles')).toBeInTheDocument();
    });

    it('muestra el error del servidor y recarga el listado tras un fallo parcial', async () => {
        vi.mocked(authService.asignarRol).mockRejectedValue(
            errorAxios(500, { detail: 'No se pudo asignar el rol' })
        );

        renderPage();

        await screen.findByText('Ana Pérez');
        fireEvent.click(
            within(filaDe('Ana Pérez')).getByRole('button', { name: 'Editar roles' })
        );
        fireEvent.click(screen.getByRole('checkbox', { name: 'Mecánico' }));
        fireEvent.click(screen.getByRole('button', { name: 'Guardar roles' }));

        expect(await screen.findByText('No se pudo asignar el rol')).toBeInTheDocument();
        // La recarga refleja lo que realmente quedó en el servidor.
        await waitFor(() => expect(authService.listarUsuarios).toHaveBeenCalledTimes(2));
    });

    it('permite reintentar la carga inicial', async () => {
        vi.mocked(authService.listarUsuarios)
            .mockRejectedValueOnce(errorAxios(500, { detail: 'Servicio no disponible' }))
            .mockResolvedValueOnce([ADMIN, ANA, MARTIN]);

        renderPage();

        expect(await screen.findByText('No se pudieron cargar los usuarios')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

        expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
    });
});
