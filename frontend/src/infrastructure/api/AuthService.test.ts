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
    // `roles` se conserva completo para las guardas multirol (D-03).
    expect(auth.user.roles).toEqual(['cliente']);
  });

  it('mapea roles[] de /auth/me a role singular', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: apiMeResponse });

    const user = await authService.getProfile();

    expect(user.role).toBe('mecanico');
    expect(user.id).toBe('2');
    expect(user.roles).toEqual(['mecanico']);
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
      roles: ['mecanico'],
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

  it('conserva todos los roles para que las guardas den acceso a cada portal (D-03)', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: usuarioConDosRoles });

    const user = await authService.getProfile();

    expect(user.roles).toEqual(['mecanico', 'administrador']);
  });

  it('descarta roles desconocidos que no forman parte del contrato', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { ...usuarioRespuestaReal, roles: ['supervisor', 'cliente'] },
    });

    const user = await authService.getProfile();

    expect(user.role).toBe('cliente');
    expect(user.roles).toEqual(['cliente']);
  });

  it('respeta is_active en false en lugar de asumir que el usuario está activo', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { ...usuarioRespuestaReal, is_active: false } });

    const user = await authService.getProfile();

    expect(user.is_active).toBe(false);
  });
});

describe('AuthService: listado administrativo de usuarios', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('consulta GET /auth/usuarios y conserva todos los roles de cada cuenta', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: [usuarioRespuestaReal, usuarioConDosRoles],
    });

    const usuarios = await authService.listarUsuarios();

    expect(apiClient.get).toHaveBeenCalledWith('/auth/usuarios');
    expect(usuarios).toEqual([
      {
        id: '42',
        email: 'mecanico@correo.cl',
        full_name: 'Martín Herrera',
        roles: ['mecanico'],
        is_active: true,
      },
      {
        id: '42',
        email: 'mecanico@correo.cl',
        full_name: 'Martín Herrera',
        roles: ['mecanico', 'administrador'],
        is_active: true,
      },
    ]);
  });

  it('normaliza roles ausentes a una lista vacía en lugar de romper el filtrado', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: [{ id: 9, email: 'sinrol@correo.cl', full_name: 'Sin Rol', is_active: true }],
    });

    const [usuario] = await authService.listarUsuarios();

    expect(usuario.roles).toEqual([]);
  });

  it('traduce el payload literal publicado por la Gateway', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: [
        {
          id: 7,
          email: 'ana@correo.cl',
          full_name: 'Ana P\u00e9rez',
          roles: ['cliente'],
          is_active: true,
        },
      ],
    });

    const [usuario] = await authService.listarUsuarios();

    expect(usuario).toEqual({
      id: '7',
      email: 'ana@correo.cl',
      full_name: 'Ana P\u00e9rez',
      roles: ['cliente'],
      is_active: true,
    });
  });
});

describe('AuthService.register: registro público vía la Gateway', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('envía solo email, password y full_name, y adapta el usuario creado', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { id: 42, email: 'ana@correo.cl', full_name: 'Ana Pérez', roles: ['cliente'], is_active: true },
    });

    const usuario = await authService.register({
      email: 'ana@correo.cl',
      password: 'clave-segura-123',
      full_name: 'Ana Pérez',
    });

    expect(apiClient.post).toHaveBeenCalledWith('/auth/register', {
      email: 'ana@correo.cl',
      password: 'clave-segura-123',
      full_name: 'Ana Pérez',
    });
    expect(usuario).toMatchObject({ id: '42', role: 'cliente', roles: ['cliente'] });
  });

  it('no reenvía campos extra aunque lleguen en el objeto (p. ej. un rol)', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { id: 1, email: 'a@b.cl', full_name: 'Ab', roles: ['cliente'], is_active: true },
    });
    const datos = { email: 'a@b.cl', password: 'clave-segura-123', full_name: 'Ab', role: 'administrador' };

    await authService.register(datos);

    const body = vi.mocked(apiClient.post).mock.calls[0][1] as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(['email', 'full_name', 'password']);
  });
});
