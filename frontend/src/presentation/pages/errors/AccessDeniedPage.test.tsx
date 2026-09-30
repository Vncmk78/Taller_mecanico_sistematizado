import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { AccessDeniedPage } from '@/presentation/pages/errors/AccessDeniedPage';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    login: vi.fn(),
    getProfile: vi.fn(() => new Promise<never>(() => {})),
  },
}));

const clientUser: User = {
  id: '2',
  email: 'cliente@taller.cl',
  full_name: 'Cliente Test',
  role: 'cliente',
  is_active: true,
};

const adminUser: User = {
  id: '1',
  email: 'admin@taller.cl',
  full_name: 'Admin Test',
  role: 'administrador',
  is_active: true,
};

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    isInitializing: false,
  });
});

interface AccessDeniedEntry {
  pathname: string;
  state?: { message?: string };
}

function renderAccessDenied(entry: string | AccessDeniedEntry, user: User) {
  useAuthStore.setState({
    user,
    token: `token-${user.role}`,
    isAuthenticated: true,
    isLoading: false,
    isInitializing: false,
  });
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<div data-testid="home-publico">Home Público</div>} />
          <Route path="/login" element={<div data-testid="login">Página de Login</div>} />
          <Route path="/admin" element={<div data-testid="panel-admin">Panel Admin</div>} />
          <Route path="/client" element={<div data-testid="panel-client">Panel Cliente</div>} />
          <Route path="/acceso-denegado" element={<AccessDeniedPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('AccessDeniedPage: pantalla de acceso denegado', () => {
  it('muestra el encabezado, el error 403 y el texto estático', () => {
    renderAccessDenied('/acceso-denegado', clientUser);

    expect(
      screen.getByRole('heading', { name: 'Acceso Denegado' })
    ).toBeInTheDocument();
    expect(screen.getByText('Error 403')).toBeInTheDocument();
    expect(
      screen.getByText(/No tienes permisos para realizar esta acción/)
    ).toBeInTheDocument();
  });

  it('muestra el mensaje entregado por la navegación', () => {
    renderAccessDenied(
      { pathname: '/acceso-denegado', state: { message: 'Solo los administradores pueden ver esto.' } },
      clientUser
    );

    expect(
      screen.getByText('Solo los administradores pueden ver esto.')
    ).toBeInTheDocument();
  });

  it('enlaza al home público desde "Volver al Inicio"', () => {
    renderAccessDenied('/acceso-denegado', clientUser);

    expect(screen.getByRole('link', { name: 'Volver al Inicio' })).toHaveAttribute('href', '/');
  });

  it('navega al panel del rol con "Ir a mi Panel"', async () => {
    renderAccessDenied('/acceso-denegado', adminUser);

    fireEvent.click(screen.getByRole('button', { name: 'Ir a mi Panel' }));

    expect(await screen.findByTestId('panel-admin')).toBeInTheDocument();
  });

  it('cierra sesión y redirige al login con "Cerrar Sesión"', async () => {
    renderAccessDenied('/acceso-denegado', clientUser);

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar Sesión' }));

    expect(await screen.findByTestId('login')).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });
});