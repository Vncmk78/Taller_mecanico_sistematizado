import type { PreparacionPerfilCliente } from '../entities/PerfilCliente';

export interface PerfilClientePort {
  /**
   * Prepara (idempotente) el perfil Cliente de MS2 del usuario autenticado.
   * La identidad sale del JWT; nunca se envía un usuario_id.
   */
  preparar(telefono?: string): Promise<PreparacionPerfilCliente>;
}
