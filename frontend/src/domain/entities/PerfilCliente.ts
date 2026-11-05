/**
 * Perfil Cliente local de MS2. Solo guarda la referencia al usuario de MS1 y un
 * teléfono opcional; el nombre y el correo oficiales siguen en MS1.
 */
export interface PerfilCliente {
  clienteId: string;
  usuarioId: string;
  telefono: string | null;
}

/** Resultado de preparar el perfil: `creado` es true si esta llamada lo creó. */
export interface PreparacionPerfilCliente {
  perfil: PerfilCliente;
  creado: boolean;
}
