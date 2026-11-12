import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import apiClient from '@/infrastructure/config/apiClient';
import { getToken } from '@/infrastructure/config/tokenStorage';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';

const originalAdapter = apiClient.defaults.adapter;

function responderConStatus(status: number): AxiosAdapter {
  return async (config: InternalAxiosRequestConfig) => {
    const response: AxiosResponse = {
      data: {},
      status,
      statusText: `Respuesta ${status}`,
      headers: {},
      config,
    };
    throw new AxiosError(
      `Request failed with status code ${status}`,
      AxiosError.ERR_BAD_RESPONSE,
      config,
      undefined,
      response
    );
  };
}

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

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
});

function TriggerForbidden() {
  return (
    <button
      onClick={() => {
        void apiClient.get('/admin/recurso').catch(() => {});
      }}
    >
      Disparar 403
    </button>
  );
}

describe('AuthProvider: ciclo de sesión frente a errores de la API', () => {
  it('con token inválido o expirado (401) limpia la sesión y redirige a /login', async () => {
    localStorage.setItem('token', 'token-expirado');
    useAuthStore.setState({
      token: 'token-expirado',
      isAuthenticated: false,
      isInitializing: true,
    });
    apiClient.defaults.adapter = responderConStatus(401);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div data-testid="login">Página de Login</div>} />
            <Route path="/acceso-denegado" element={<div data-testid="access-denied">Acceso Denegado</div>} />
            <Route path="/admin" element={<div data-testid="admin-panel">Panel Administrador</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByTestId('login')).toBeInTheDocument());

    expect(screen.queryByTestId('admin-panel')).not.toBeInTheDocument();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('una respuesta 403 redirige a /acceso-denegado', async () => {
    useAuthStore.setState({
      user: adminUser,
      token: 'token-admin',
      isAuthenticated: true,
      isInitializing: false,
    });
    apiClient.defaults.adapter = responderConStatus(403);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div data-testid="login">Página de Login</div>} />
            <Route path="/acceso-denegado" element={<div data-testid="access-denied">Acceso Denegado</div>} />
            <Route path="/admin" element={<TriggerForbidden />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Disparar 403' }));

    await waitFor(() => expect(screen.getByTestId('access-denied')).toBeInTheDocument());
    expect(screen.queryByTestId('login')).not.toBeInTheDocument();
  });

  it('conserva la ruta pedida aunque lleguen dos 401 seguidos (StrictMode)', async () => {
    localStorage.setItem('token', 'token-expirado');
    useAuthStore.setState({ token: 'token-expirado', isAuthenticated: true, isInitializing: true });
    apiClient.defaults.adapter = responderConStatus(401);

    function Login() {
      const location = useLocation();
      const desde = (location.state as { from?: string } | null)?.from;
      return <div data-testid="login">Volver a: {desde}</div>;
    }

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/admin/configuracion?vista=1']}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/admin/configuracion" element={<div>Configuración</div>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>
    );

    await waitFor(() => expect(screen.getByTestId('login')).toHaveTextContent('Volver a: /admin/configuracion?vista=1'));
    // Un 401 posterior estando ya en /login no reemplaza la ruta guardada.
    await apiClient.get('/auth/me').catch(() => {});
    expect(screen.getByTestId('login')).toHaveTextContent('Volver a: /admin/configuracion?vista=1');
  });

  it('restaura la sesión una sola vez aunque StrictMode repita el efecto', async () => {
    localStorage.setItem('token', 'token-valido');
    useAuthStore.setState({ token: 'token-valido', isAuthenticated: true, isInitializing: true });
    let llamadas = 0;
    apiClient.defaults.adapter = async (config) => {
      llamadas += 1;
      return { data: { id: 1, email: 'admin@taller.cl', full_name: 'Admin', roles: ['administrador'], is_active: true },
        status: 200, statusText: 'OK', headers: {}, config };
    };

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/admin']}>
          <AuthProvider>
            <Routes>
              <Route path="/admin" element={<div>Panel</div>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>
    );

    await waitFor(() => expect(useAuthStore.getState().user?.email).toBe('admin@taller.cl'));
    expect(llamadas).toBe(1);
  });

  it('marca sesionExpirada cuando expira el token de una sesión activa', async () => {
    localStorage.setItem('token', 'token-admin');
    useAuthStore.setState({
      // Sin usuario en memoria: restoreSession consulta /auth/me (si ya hubiera
      // user, hace early return y no habría petición que expirar).
      token: 'token-admin',
      isAuthenticated: true,
      isInitializing: true,
    });
    apiClient.defaults.adapter = responderConStatus(401);

    function Login() {
      const location = useLocation();
      const expiro = (location.state as { sesionExpirada?: boolean } | null)?.sesionExpirada;
      return <div data-testid="login">expirada: {String(expiro)}</div>;
    }

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/admin" element={<div>Panel</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // La restauración del montaje dispara el 401 con la sesión aún activa.
    await waitFor(() => expect(screen.getByTestId('login')).toHaveTextContent('expirada: true'));
  });

  it('un 401 durante la restauración sin sesión activa no marca sesionExpirada', async () => {
    localStorage.setItem('token', 'token-expirado');
    useAuthStore.setState({ token: 'token-expirado', isAuthenticated: false, isInitializing: true });
    apiClient.defaults.adapter = responderConStatus(401);

    function Login() {
      const location = useLocation();
      const expiro = (location.state as { sesionExpirada?: boolean } | null)?.sesionExpirada;
      return <div data-testid="login">expirada: {String(expiro)}</div>;
    }

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/admin" element={<div>Panel</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // Abrir la app con un token ya vencido no debe anunciarse como expiración.
    await waitFor(() => expect(screen.getByTestId('login')).toHaveTextContent('expirada: false'));
  });
});
