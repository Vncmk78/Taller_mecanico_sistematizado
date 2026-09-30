import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { AuthResponse, User } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';

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

const mechanicUser: User = {
  id: '3',
  email: 'mecanico@taller.cl',
  full_name: 'Mecánico Test',
  role: 'mecanico',
  is_active: true,
};

function authResponse(user: User): AuthResponse {
  return { access_token: `token-${user.role}`, token_type: 'bearer', user };
}

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    isInitializing: false,
  });
  vi.clearAllMocks();
});

function renderLogin(entry: { pathname: string; state?: unknown } = { pathname: '/login' }) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Home</div>} />
          <Route path="/admin" element={<div data-testid="home-admin">Portal Administrador</div>} />
          <Route path="/client" element={<div data-testid="home-client">Portal Cliente</div>} />
          <Route path="/client/vehiculos" element={<div data-testid="home-client-vehiculos">Mis Vehículos</div>} />
          <Route path="/mechanic" element={<div data-testid="home-mechanic">Portal Mecánico</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

async function completarLogin(email: string, password: string) {
  fireEvent.change(screen.getByLabelText('Correo Electrónico'), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText('Contraseña'), {
    target: { value: password },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Ingresar a mi cuenta' }));
}

describe('LoginPage: flujo funcional de inicio de sesión', () => {
  it('inicia sesión como cliente y navega a /client', async () => {
    vi.mocked(authService.login).mockResolvedValue(authResponse(clientUser));
    renderLogin();

    await completarLogin('cliente@taller.cl', 'ClientePrueba123!');

    expect(await screen.findByTestId('home-client')).toBeInTheDocument();
  });

  it('inicia sesión como mecánico y navega a /mechanic', async () => {
    vi.mocked(authService.login).mockResolvedValue(authResponse(mechanicUser));
    renderLogin();

    await completarLogin('mecanico@taller.cl', 'MecanicoPrueba123!');

    expect(await screen.findByTestId('home-mechanic')).toBeInTheDocument();
  });

  it('inicia sesión como administrador y navega a /admin', async () => {
    vi.mocked(authService.login).mockResolvedValue(authResponse(adminUser));
    renderLogin();

    await completarLogin('admin@taller.cl', 'AdminPrueba123!');

    expect(await screen.findByTestId('home-admin')).toBeInTheDocument();
  });

  it('vuelve a la ruta protegida que se intentaba abrir (state.from)', async () => {
    vi.mocked(authService.login).mockResolvedValue(authResponse(clientUser));
    renderLogin({ pathname: '/login', state: { from: '/client/vehiculos' } });

    await completarLogin('cliente@taller.cl', 'ClientePrueba123!');

    expect(await screen.findByTestId('home-client-vehiculos')).toBeInTheDocument();
  });

  it('muestra el detalle de la API y permanece en /login con credenciales inválidas', async () => {
    const error = new AxiosError(
      'Request failed with status code 401',
      AxiosError.ERR_BAD_RESPONSE,
      undefined,
      undefined,
      {
        status: 401,
        statusText: 'Unauthorized',
        headers: {},
        config: {} as InternalAxiosRequestConfig,
        data: { detail: 'Correo o contraseña inválidos' },
      }
    );
    vi.mocked(authService.login).mockRejectedValue(error);
    renderLogin();

    await completarLogin('cliente@taller.cl', 'clave-incorrecta');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Correo o contraseña inválidos'
    );
    expect(screen.getByRole('heading', { name: 'Iniciar Sesión' })).toBeInTheDocument();
    expect(screen.queryByTestId('home-client')).not.toBeInTheDocument();
  });

  it('valida el correo vacío antes de llamar a la API', async () => {
    renderLogin();

    await completarLogin('', 'ClientePrueba123!');

    expect(await screen.findByText('Ingrese un correo válido')).toBeInTheDocument();
    expect(authService.login).not.toHaveBeenCalled();
  });

  it('valida el largo mínimo de la contraseña antes de llamar a la API', async () => {
    renderLogin();

    await completarLogin('cliente@taller.cl', '123');

    expect(
      await screen.findByText('La contraseña debe tener al menos 6 caracteres')
    ).toBeInTheDocument();
    expect(authService.login).not.toHaveBeenCalled();
  });

  it('alterna la visibilidad de la contraseña', () => {
    renderLogin();

    const passwordInput = screen.getByLabelText('Contraseña') as HTMLInputElement;
    expect(passwordInput.type).toBe('password');

    fireEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }));

    expect(passwordInput.type).toBe('text');
  });
});