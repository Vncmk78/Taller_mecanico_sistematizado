import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AuthResponse, User } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { getToken } from '@/infrastructure/config/tokenStorage';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    login: vi.fn(),
    getProfile: vi.fn(),
  },
}));

const clientUser: User = {
  id: '2',
  email: 'cliente@taller.cl',
  full_name: 'Cliente Test',
  role: 'cliente',
  is_active: true,
};

const authResponse: AuthResponse = {
  access_token: 'token-cliente',
  token_type: 'bearer',
  user: clientUser,
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
  vi.clearAllMocks();
});

describe('useAuthStore: flujo funcional de autenticación', () => {
  it('inicia sesión con éxito, guarda el token y autentica al usuario', async () => {
    vi.mocked(authService.login).mockResolvedValue(authResponse);

    const user = await useAuthStore
      .getState()
      .login('cliente@taller.cl', 'ClientePrueba123!');

    expect(user).toEqual(clientUser);
    expect(getToken()).toBe('token-cliente');
    expect(useAuthStore.getState().user).toEqual(clientUser);
    expect(useAuthStore.getState().token).toBe('token-cliente');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it('con credenciales inválidas propaga el error y no deja sesión activa', async () => {
    vi.mocked(authService.login).mockRejectedValue(new Error('Credenciales incorrectas'));

    await expect(
      useAuthStore.getState().login('cliente@taller.cl', 'clave-incorrecta')
    ).rejects.toThrow('Credenciales incorrectas');

    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it('restaura una sesión válida consultando el perfil', async () => {
    vi.mocked(authService.getProfile).mockResolvedValue(clientUser);
    localStorage.setItem('token', 'token-cliente');
    useAuthStore.setState({
      token: 'token-cliente',
      isAuthenticated: false,
      isInitializing: true,
    });

    await useAuthStore.getState().restoreSession();

    expect(useAuthStore.getState().user).toEqual(clientUser);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().isInitializing).toBe(false);
  });

  it('descarta la sesión cuando el perfil responde con token inválido o expirado', async () => {
    vi.mocked(authService.getProfile).mockRejectedValue(
      new Error('Token inválido o expirado')
    );
    localStorage.setItem('token', 'token-expirado');
    useAuthStore.setState({
      token: 'token-expirado',
      isAuthenticated: false,
      isInitializing: true,
    });

    await useAuthStore.getState().restoreSession();

    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isInitializing).toBe(false);
  });

  it('sin token no consulta el perfil y finaliza la inicialización', async () => {
    await useAuthStore.getState().restoreSession();

    expect(authService.getProfile).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isInitializing).toBe(false);
  });

  it('cerrar sesión elimina el token y la sesión', () => {
    localStorage.setItem('token', 'token-cliente');
    useAuthStore.setState({
      user: clientUser,
      token: 'token-cliente',
      isAuthenticated: true,
    });

    useAuthStore.getState().logout();

    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('clearSession limpia la sesión para un token expirado', () => {
    localStorage.setItem('token', 'token-expirado');
    useAuthStore.setState({
      user: clientUser,
      token: 'token-expirado',
      isAuthenticated: true,
    });

    useAuthStore.getState().clearSession();

    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});