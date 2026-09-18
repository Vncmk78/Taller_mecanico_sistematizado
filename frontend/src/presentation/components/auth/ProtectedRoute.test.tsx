import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { User, UserRole } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { ProtectedRoute } from '@/presentation/components/auth/ProtectedRoute';

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

interface RenderProtectedRouteOptions {
  entry: string;
  allowedRoles?: UserRole[];
}

function renderProtectedRoute({ entry, allowedRoles }: RenderProtectedRouteOptions) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div data-testid="login">Página de Login</div>} />
          <Route path="/client" element={<div data-testid="home-client">Portal Cliente</div>} />
          <Route path="/mechanic" element={<div data-testid="home-mechanic">Portal Mecánico</div>} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={allowedRoles}>
                <div data-testid="admin-panel">Panel Administrador</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('ProtectedRoute: acceso a rutas protegidas', () => {
  it('redirige a /login cuando el usuario no está autenticado', () => {
    renderProtectedRoute({ entry: '/admin', allowedRoles: ['administrador'] });

    expect(screen.getByTestId('login')).toBeInTheDocument();
    expect(screen.queryByTestId('admin-panel')).not.toBeInTheDocument();
  });

  it('muestra el loader mientras la sesión está en inicialización', () => {
    useAuthStore.setState({
      user: null,
      token: 'token-valido',
      isAuthenticated: false,
      isInitializing: true,
    });

    renderProtectedRoute({ entry: '/admin', allowedRoles: ['administrador'] });

    expect(screen.getByText('Verificando sesión...')).toBeInTheDocument();
    expect(screen.queryByTestId('admin-panel')).not.toBeInTheDocument();
  });

  it('permite el acceso cuando el rol está permitido', () => {
    useAuthStore.setState({
      user: adminUser,
      token: 'token-admin',
      isAuthenticated: true,
    });

    renderProtectedRoute({ entry: '/admin', allowedRoles: ['administrador'] });

    expect(screen.getByTestId('admin-panel')).toBeInTheDocument();
  });

  it('redirige al panel del rol cuando no tiene permisos para la ruta', () => {
    useAuthStore.setState({
      user: clientUser,
      token: 'token-cliente',
      isAuthenticated: true,
    });

    renderProtectedRoute({ entry: '/admin', allowedRoles: ['administrador'] });

    expect(screen.getByTestId('home-client')).toBeInTheDocument();
    expect(screen.queryByTestId('admin-panel')).not.toBeInTheDocument();
  });
});