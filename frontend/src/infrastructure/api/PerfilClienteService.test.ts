import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { perfilClienteService } from '@/infrastructure/api/PerfilClienteService';

vi.mock('@/infrastructure/config/apiClient', () => ({
  default: { post: vi.fn() },
}));

const perfilApi = { cliente_id: 7, usuario_id: 42, telefono: '+56 9 1234 5678' };

describe('PerfilClienteService: POST /api/clientes/perfil vía la Gateway', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sin teléfono envía un body vacío (nunca un usuario_id)', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ status: 200, data: { ...perfilApi, telefono: null } });

    const resultado = await perfilClienteService.preparar();

    expect(apiClient.post).toHaveBeenCalledWith('/clientes/perfil', {});
    expect(resultado).toEqual({
      perfil: { clienteId: '7', usuarioId: '42', telefono: null },
      creado: false,
    });
  });

  it('con teléfono lo envía y reconoce el 201 como perfil creado', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ status: 201, data: perfilApi });

    const resultado = await perfilClienteService.preparar('+56 9 1234 5678');

    expect(apiClient.post).toHaveBeenCalledWith('/clientes/perfil', { telefono: '+56 9 1234 5678' });
    expect(resultado.creado).toBe(true);
    expect(resultado.perfil.telefono).toBe('+56 9 1234 5678');
  });
});
