import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { perfilClienteService } from '@/infrastructure/api/PerfilClienteService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { usePerfilClienteStore } from '@/infrastructure/stores/usePerfilClienteStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { ClientProfileGate } from '@/presentation/components/auth/ClientProfileGate';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: { login: vi.fn(), getProfile: vi.fn(() => new Promise<never>(() => {})) },
}));

vi.mock('@/infrastructure/api/PerfilClienteService', () => ({
  perfilClienteService: { preparar: vi.fn() },
}));

const cliente: User = {
  id: '42',
  email: 'Ana@Correo.cl',
  full_name: 'Ana Pérez',
  role: 'cliente',
  roles: ['cliente'],
  is_active: true,
};

const preparacion = (creado: boolean) => ({
  perfil: { clienteId: '7', usuarioId: '42', telefono: null },
  creado,
});

function errorHttp(status: number, data: unknown = {}): AxiosError {
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
  return new AxiosError('fallo', String(status), config, undefined, {
    status, statusText: '', headers: {}, config, data,
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  usePerfilClienteStore.getState().reset();
  useAuthStore.setState({
    user: cliente,
    token: 'token-cliente',
    isAuthenticated: true,
    isLoading: false,
    isInitializing: false,
  });
});

function renderGate() {
  return render(
    <MemoryRouter initialEntries={['/client']}>
      <AuthProvider>
        <Routes>
          <Route
            path="/client"
            element={
              <ClientProfileGate>
                <div>Portal del cliente</div>
              </ClientProfileGate>
            }
          />
          <Route path="/login" element={<div>Pantalla de login</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('ClientProfileGate: perfil Cliente de MS2 tras iniciar sesión', () => {
  it('prepara el perfil una sola vez y luego muestra el portal', async () => {
    vi.mocked(perfilClienteService.preparar).mockResolvedValue(preparacion(true));
    const { rerender } = renderGate();

    expect(screen.getByText('Preparando tu perfil de cliente...')).toBeInTheDocument();
    expect(await screen.findByText('Portal del cliente')).toBeInTheDocument();
    rerender(
      <MemoryRouter initialEntries={['/client']}>
        <AuthProvider>
          <ClientProfileGate>
            <div>Portal del cliente</div>
          </ClientProfileGate>
        </AuthProvider>
      </MemoryRouter>
    );
    expect(perfilClienteService.preparar).toHaveBeenCalledTimes(1);
    expect(perfilClienteService.preparar).toHaveBeenCalledWith(undefined);
  });

  it('envía el teléfono del registro solo para la misma cuenta y lo olvida al terminar', async () => {
    usePerfilClienteStore.getState().recordarTelefono('ana@correo.cl', '+56 9 1234 5678');
    vi.mocked(perfilClienteService.preparar).mockResolvedValue(preparacion(true));
    renderGate();

    await screen.findByText('Portal del cliente');
    expect(perfilClienteService.preparar).toHaveBeenCalledWith('+56 9 1234 5678');
    expect(usePerfilClienteStore.getState().telefonoPendiente).toBeNull();
  });

  it('no usa el teléfono pendiente de otra cuenta', async () => {
    usePerfilClienteStore.getState().recordarTelefono('otra@correo.cl', '+56 9 0000 0000');
    vi.mocked(perfilClienteService.preparar).mockResolvedValue(preparacion(false));
    renderGate();

    await screen.findByText('Portal del cliente');
    expect(perfilClienteService.preparar).toHaveBeenCalledWith(undefined);
  });

  it('si falla informa que la cuenta existe y permite reintentar', async () => {
    vi.mocked(perfilClienteService.preparar)
      .mockRejectedValueOnce(errorHttp(500, { detail: 'No fue posible preparar el perfil de cliente' }))
      .mockResolvedValueOnce(preparacion(true));
    renderGate();

    expect(await screen.findByRole('heading', { name: 'Tu cuenta ya está creada' })).toBeInTheDocument();
    expect(screen.getByText('No fue posible preparar el perfil de cliente')).toBeInTheDocument();
    expect(screen.queryByText('Portal del cliente')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByText('Portal del cliente')).toBeInTheDocument();
    expect(perfilClienteService.preparar).toHaveBeenCalledTimes(2);
  });

  it('sin conexión muestra el mensaje de conexión y conserva la sesión', async () => {
    vi.mocked(perfilClienteService.preparar).mockRejectedValue(errorHttp(502));
    renderGate();

    expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('tras cerrar sesión y volver a entrar, vuelve a intentar la preparación', async () => {
    vi.mocked(perfilClienteService.preparar)
      .mockRejectedValueOnce(errorHttp(500))
      .mockResolvedValueOnce(preparacion(false));
    const { unmount } = renderGate();

    fireEvent.click(await screen.findByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByText('Pantalla de login')).toBeInTheDocument();
    expect(usePerfilClienteStore.getState().estado).toBe('pendiente');
    unmount();

    useAuthStore.setState({ user: cliente, token: 'token-nuevo', isAuthenticated: true });
    renderGate();

    expect(await screen.findByText('Portal del cliente')).toBeInTheDocument();
    expect(perfilClienteService.preparar).toHaveBeenCalledTimes(2);
  });

  it('un 409 (perfil existente con otro teléfono) deja continuar con un aviso', async () => {
    usePerfilClienteStore.getState().recordarTelefono('ana@correo.cl', '+56 9 2222 2222');
    vi.mocked(perfilClienteService.preparar).mockRejectedValue(
      errorHttp(409, { detail: 'El perfil Cliente ya existe con otro teléfono; no se modificó' })
    );
    renderGate();

    expect(await screen.findByText('Portal del cliente')).toBeInTheDocument();
    expect(screen.getByText(/ya existía con otro teléfono/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Entendido' }));
    await waitFor(() =>
      expect(screen.queryByText(/ya existía con otro teléfono/)).not.toBeInTheDocument()
    );
  });
});
