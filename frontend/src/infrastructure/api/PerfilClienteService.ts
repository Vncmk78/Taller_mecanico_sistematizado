import type { PreparacionPerfilCliente } from '@/domain/entities/PerfilCliente';
import type { PerfilClientePort } from '@/domain/ports/PerfilClientePort';
import apiClient from '../config/apiClient';

// Contrato de MS2 vía la Gateway: POST /api/clientes/perfil.
// 201 = esta llamada creó el perfil; 200 = ya existía (sin cambios).
interface PerfilClienteApi {
  cliente_id: number;
  usuario_id: number;
  telefono: string | null;
}

class PerfilClienteService implements PerfilClientePort {
  async preparar(telefono?: string): Promise<PreparacionPerfilCliente> {
    // Sin teléfono se envía {}: no significa "borrar", solo "no lo informo".
    const body = telefono ? { telefono } : {};
    const respuesta = await apiClient.post<PerfilClienteApi>('/clientes/perfil', body);
    const { data } = respuesta;
    return {
      perfil: {
        clienteId: String(data.cliente_id),
        usuarioId: String(data.usuario_id),
        telefono: data.telefono,
      },
      creado: respuesta.status === 201,
    };
  }
}

export const perfilClienteService = new PerfilClienteService();
