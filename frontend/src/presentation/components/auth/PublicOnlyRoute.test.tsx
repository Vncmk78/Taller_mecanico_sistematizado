import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { PublicOnlyRoute } from '@/presentation/components/auth/PublicOnlyRoute';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    login: vi.fn(),
    getProfile: vi.fn(() => new Promise<never>(() => {})),
  },
}));

const adminUser: User = {
  id: '1',
  email: 'admin@taller.cl',
  full_name: 'Admin Test',
  role: 'administrador',
  is_active: true,
};

const clientUser: User = {
  id: '2',
  email: 'cliente@taller.cl',
  full_name: 'Cliente Test',
  role: 'cliente',
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

function renderPublicOnlyRoute(entry = '/login') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<PublicOnlyRoute><div data-testid="login-page">Página de Login</div></PublicOnlyRoute>} />
          <Route path="/admin" element={<div data-testid="home-admin">Panel Administrador</div>} />
          <Route path="/client" element={<div data-testid="home-client">Portal Cliente</div>} />
          <Route path="/mechanic" element={<div data-testid="home-mechanic">Portal Mecánico</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('PublicOnlyRoute: guarda de rutas públicas', () => {
  it('permite el acceso al login cuando el usuario no está autenticado', () => {
    renderPublicOnlyRoute();

    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });

  it('muestra el loader mientras la sesión está en inicialización', () => {
    useAuthStore.setState({
      user: null,
      token: 'token-valido',
      isAuthenticated: false,
      isInitializing: true,
    });

    renderPublicOnlyRoute();

    expect(screen.getByText('Verificando sesión...')).toBeInTheDocument();
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
  });

  it('redirige al panel del administrador cuando ya está autenticado', () => {
    useAuthStore.setState({
      user: adminUser,
      token: 'token-admin',
      isAuthenticated: true,
    });

    renderPublicOnlyRoute();

    expect(screen.getByTestId('home-admin')).toBeInTheDocument();
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
  });

  it('redirige al portal del cliente cuando ya está autenticado', () => {
    useAuthStore.setState({
      user: clientUser,
      token: 'token-cliente',
      isAuthenticated: true,
    });

    renderPublicOnlyRoute();

    expect(screen.getByTestId('home-client')).toBeInTheDocument();
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
  });
});