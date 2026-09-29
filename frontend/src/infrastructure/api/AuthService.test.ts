import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authService } from '@/infrastructure/api/AuthService';
import apiClient from '@/infrastructure/config/apiClient';

vi.mock('@/infrastructure/config/apiClient', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

const apiAuthResponse = {
  access_token: 'token-abc',
  token_type: 'bearer',
  user: {
    id: 1,
    email: 'cliente@pruebas.cl',
    full_name: 'Cliente de Prueba',
    roles: ['cliente'],
    is_active: true,
  },
};

const apiMeResponse = {
  id: 2,
  email: 'mecanico@pruebas.cl',
  full_name: 'Mecánico de Prueba',
  roles: ['mecanico'],
  is_active: true,
};

describe('AuthService: adapta la respuesta de MS1 al dominio', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('mapea roles[] del login a role singular para redirigir al portal correcto', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: apiAuthResponse });

    const auth = await authService.login({ email: 'cliente@pruebas.cl', password: 'ClientePrueba123!' });

    expect(auth.user.role).toBe('cliente');
    expect(auth.user).not.toHaveProperty('roles');
  });

  it('mapea roles[] de /auth/me a role singular', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: apiMeResponse });

    const user = await authService.getProfile();

    expect(user.role).toBe('mecanico');
    expect(user.id).toBe('2');
    expect(user).not.toHaveProperty('roles');
  });
});