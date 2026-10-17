import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authService } from '@/infrastructure/api/AuthService';
import apiClient from '@/infrastructure/config/apiClient';
import {
  tokenRespuestaReal,
  usuarioConDosRoles,
  usuarioRespuestaReal,
} from '@/infrastructure/mocks/payloads.reales';

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

// Cuerpos literales de gateway/contratos/auth.py.
describe('AuthService: mapeo contra el payload real de MS1', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('traduce el token real de ejemplo, con el usuario anidado', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: tokenRespuestaReal });

    const auth = await authService.login({ email: 'ana@correo.cl', password: 'ClaveDePrueba123!' });

    expect(auth.access_token).toBe(tokenRespuestaReal.access_token);
    expect(auth.token_type).toBe('bearer');
    expect(auth.user.id).toBe('7');
    expect(auth.user.email).toBe('ana@correo.cl');
    expect(auth.user.full_name).toBe('Ana Pérez');
    expect(auth.user.role).toBe('cliente');
    expect(auth.user.is_active).toBe(true);
  });

  it('traduce el cuerpo real de /auth/me de un mecánico', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: usuarioRespuestaReal });

    const user = await authService.getProfile();

    expect(user).toEqual({
      id: '42',
      email: 'mecanico@correo.cl',
      full_name: 'Martín Herrera',
      role: 'mecanico',
      is_active: true,
    });
  });

  it('con varios roles en la lista toma el primero, que define el portal de ingreso', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: usuarioConDosRoles });

    const user = await authService.getProfile();

    // roles es una lista en el contrato, así que puede traer más de uno. El
    // dominio tiene un único `role`, y hoy gana el primero: queda fijado aquí
    // para que la decisión sea explícita y no un accidente del mapeo.
    expect(user.role).toBe('mecanico');
  });

  it('respeta is_active en false en lugar de asumir que el usuario está activo', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { ...usuarioRespuestaReal, is_active: false } });

    const user = await authService.getProfile();

    expect(user.is_active).toBe(false);
  });
});
